import csv
from django.db.models import Count, Q
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import generics, status, views
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .alert_engine import run_all_checks
from .models import Alert, Equipment, InspectionRecord, MaintenancePlan, User
from .permissions import IsAdmin, IsAdminOrFieldStaff, IsAdminOrObserver, IsNotObserver
from .serializers import (
    AlertCloseRequestSerializer,
    AlertConfirmCloseSerializer,
    AlertSerializer,
    EquipmentSerializer,
    InspectionRecordSerializer,
    MaintenancePlanSerializer,
    UserCreateSerializer,
    UserSerializer,
)


class UserListCreateView(generics.ListCreateAPIView):
    queryset = User.objects.all()

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return UserCreateSerializer
        return UserSerializer

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAdmin()]
        return [IsAdmin()]


class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = User.objects.all()

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return UserCreateSerializer
        return UserSerializer

    def get_permissions(self):
        return [IsAdmin()]


class EquipmentListCreateView(generics.ListCreateAPIView):
    queryset = Equipment.objects.all()
    serializer_class = EquipmentSerializer
    filterset_fields = ['status', 'category', 'responsible_person']
    search_fields = ['name', 'code', 'location']

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAdmin()]
        return [IsNotObserver()]


class EquipmentDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Equipment.objects.all()
    serializer_class = EquipmentSerializer

    def get_permissions(self):
        if self.request.method in ['PUT', 'PATCH', 'DELETE']:
            return [IsAdmin()]
        return [IsNotObserver()]


class MaintenancePlanListCreateView(generics.ListCreateAPIView):
    queryset = MaintenancePlan.objects.all()
    serializer_class = MaintenancePlanSerializer
    filterset_fields = ['equipment', 'is_active']

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAdmin()]
        return [IsNotObserver()]


class MaintenancePlanDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = MaintenancePlan.objects.all()
    serializer_class = MaintenancePlanSerializer

    def get_permissions(self):
        if self.request.method in ['PUT', 'PATCH', 'DELETE']:
            return [IsAdmin()]
        return [IsNotObserver()]


class InspectionRecordListCreateView(generics.ListCreateAPIView):
    queryset = InspectionRecord.objects.all()
    serializer_class = InspectionRecordSerializer
    filterset_fields = ['equipment', 'status', 'inspector']

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAdminOrFieldStaff()]
        return [IsNotObserver()]

    def perform_create(self, serializer):
        serializer.save(inspector=self.request.user)


class InspectionRecordDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = InspectionRecord.objects.all()
    serializer_class = InspectionRecordSerializer

    def get_permissions(self):
        if self.request.method in ['PUT', 'PATCH']:
            return [IsAdminOrFieldStaff()]
        if self.request.method == 'DELETE':
            return [IsAdmin()]
        return [IsNotObserver()]


class AlertListView(generics.ListAPIView):
    queryset = Alert.objects.all()
    serializer_class = AlertSerializer
    filterset_fields = ['equipment', 'alert_type', 'status', 'assigned_to']
    search_fields = ['title', 'description']
    permission_classes = [IsAuthenticated]


class AlertDetailView(generics.RetrieveAPIView):
    queryset = Alert.objects.all()
    serializer_class = AlertSerializer
    permission_classes = [IsAuthenticated]


class AlertCloseRequestView(views.APIView):
    permission_classes = [IsAdminOrFieldStaff]

    def post(self, request, pk):
        try:
            alert = Alert.objects.get(pk=pk)
        except Alert.DoesNotExist:
            return Response({'detail': '提醒不存在'}, status=status.HTTP_404_NOT_FOUND)

        if alert.status == Alert.STATUS_CLOSED:
            return Response({'detail': '该提醒已关闭'}, status=status.HTTP_400_BAD_REQUEST)

        if alert.status == Alert.STATUS_PROCESSING:
            return Response({'detail': '该提醒已在处理中，等待管理员确认'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = AlertCloseRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        alert.status = Alert.STATUS_PROCESSING
        alert.close_request_note = serializer.validated_data['close_request_note']
        alert.close_requested_at = timezone.now()
        alert.close_requested_by = request.user
        alert.save()

        return Response(AlertSerializer(alert).data)


class AlertConfirmCloseView(views.APIView):
    permission_classes = [IsAdmin]

    def post(self, request, pk):
        try:
            alert = Alert.objects.get(pk=pk)
        except Alert.DoesNotExist:
            return Response({'detail': '提醒不存在'}, status=status.HTTP_404_NOT_FOUND)

        if alert.status == Alert.STATUS_CLOSED:
            return Response({'detail': '该提醒已关闭'}, status=status.HTTP_400_BAD_REQUEST)

        if alert.status != Alert.STATUS_PROCESSING:
            return Response({'detail': '该提醒尚未提交关闭申请'}, status=status.HTTP_400_BAD_REQUEST)

        alert.status = Alert.STATUS_CLOSED
        alert.confirmed_at = timezone.now()
        alert.confirmed_by = request.user
        alert.save()

        return Response(AlertSerializer(alert).data)


class AlertRunChecksView(views.APIView):
    permission_classes = [IsAdmin]

    def post(self, request):
        created = run_all_checks()
        return Response({
            'generated_count': len(created),
            'alerts': AlertSerializer(created, many=True).data,
        })


class StatsByEquipmentView(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        equipment_id = request.query_params.get('equipment')
        queryset = Alert.objects.all()
        if equipment_id:
            queryset = queryset.filter(equipment_id=equipment_id)

        stats = queryset.values(
            'equipment__id', 'equipment__name', 'equipment__code'
        ).annotate(
            total=Count('id'),
            open_count=Count('id', filter=Q(status=Alert.STATUS_OPEN)),
            processing_count=Count('id', filter=Q(status=Alert.STATUS_PROCESSING)),
            closed_count=Count('id', filter=Q(status=Alert.STATUS_CLOSED)),
        ).order_by('-total')

        return Response(list(stats))


class StatsByResponsiblePersonView(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user_id = request.query_params.get('user')
        queryset = Alert.objects.all()
        if user_id:
            queryset = queryset.filter(assigned_to_id=user_id)

        stats = queryset.values(
            'assigned_to__id', 'assigned_to__username'
        ).annotate(
            total=Count('id'),
            open_count=Count('id', filter=Q(status=Alert.STATUS_OPEN)),
            processing_count=Count('id', filter=Q(status=Alert.STATUS_PROCESSING)),
            closed_count=Count('id', filter=Q(status=Alert.STATUS_CLOSED)),
        ).order_by('-total')

        return Response(list(stats))


class _ExportMixin:
    def _build_alert_queryset(self, request):
        queryset = Alert.objects.select_related('equipment', 'assigned_to', 'close_requested_by', 'confirmed_by').all()
        equipment_id = request.query_params.get('equipment')
        alert_type = request.query_params.get('alert_type')
        alert_status = request.query_params.get('status')
        if equipment_id:
            queryset = queryset.filter(equipment_id=equipment_id)
        if alert_type:
            queryset = queryset.filter(alert_type=alert_type)
        if alert_status:
            queryset = queryset.filter(status=alert_status)
        return queryset


class ExportAlertsCsvView(views.APIView, _ExportMixin):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = self._build_alert_queryset(request)
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="alerts_export.csv"'
        writer = csv.writer(response)
        writer.writerow([
            'ID', '器械编号', '器械名称', '提醒类型', '标题', '描述',
            '状态', '指派处理人', '关闭申请说明', '关闭申请人', '关闭申请时间',
            '确认关闭人', '确认关闭时间', '创建时间',
        ])
        for alert in queryset:
            writer.writerow([
                alert.id,
                alert.equipment.code,
                alert.equipment.name,
                alert.get_alert_type_display(),
                alert.title,
                alert.description,
                alert.get_status_display(),
                alert.assigned_to.username if alert.assigned_to else '',
                alert.close_request_note,
                alert.close_requested_by.username if alert.close_requested_by else '',
                alert.close_requested_at.strftime('%Y-%m-%d %H:%M:%S') if alert.close_requested_at else '',
                alert.confirmed_by.username if alert.confirmed_by else '',
                alert.confirmed_at.strftime('%Y-%m-%d %H:%M:%S') if alert.confirmed_at else '',
                alert.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            ])
        return response


class ExportStatsByEquipmentCsvView(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        equipment_id = request.query_params.get('equipment')
        queryset = Alert.objects.all()
        if equipment_id:
            queryset = queryset.filter(equipment_id=equipment_id)

        stats = queryset.values(
            'equipment__id', 'equipment__name', 'equipment__code'
        ).annotate(
            total=Count('id'),
            open_count=Count('id', filter=Q(status=Alert.STATUS_OPEN)),
            processing_count=Count('id', filter=Q(status=Alert.STATUS_PROCESSING)),
            closed_count=Count('id', filter=Q(status=Alert.STATUS_CLOSED)),
        ).order_by('-total')

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="stats_by_equipment.csv"'
        writer = csv.writer(response)
        writer.writerow(['器械ID', '器械编号', '器械名称', '总数', '待处理', '处理中', '已关闭'])
        for row in stats:
            writer.writerow([
                row['equipment__id'],
                row['equipment__code'],
                row['equipment__name'],
                row['total'],
                row['open_count'],
                row['processing_count'],
                row['closed_count'],
            ])
        return response


class ExportStatsByPersonCsvView(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user_id = request.query_params.get('user')
        queryset = Alert.objects.all()
        if user_id:
            queryset = queryset.filter(assigned_to_id=user_id)

        stats = queryset.values(
            'assigned_to__id', 'assigned_to__username'
        ).annotate(
            total=Count('id'),
            open_count=Count('id', filter=Q(status=Alert.STATUS_OPEN)),
            processing_count=Count('id', filter=Q(status=Alert.STATUS_PROCESSING)),
            closed_count=Count('id', filter=Q(status=Alert.STATUS_CLOSED)),
        ).order_by('-total')

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="stats_by_person.csv"'
        writer = csv.writer(response)
        writer.writerow(['责任人ID', '责任人用户名', '总数', '待处理', '处理中', '已关闭'])
        for row in stats:
            writer.writerow([
                row['assigned_to__id'] or '',
                row['assigned_to__username'] or '(未指派)',
                row['total'],
                row['open_count'],
                row['processing_count'],
                row['closed_count'],
            ])
        return response
