from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import generics, status, views
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .alert_engine import run_all_checks
from .models import Alert, Equipment, InspectionRecord, MaintenancePlan, User
from .permissions import (
    IsAdmin,
    IsAdminOrFieldStaff,
    IsAdminOrObserver,
    IsFieldStaff,
    ReadOnlyIfObserver,
)
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
        return [IsAuthenticated()]


class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = User.objects.all()

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return UserCreateSerializer
        return UserSerializer

    def get_permissions(self):
        if self.request.method in ['PUT', 'PATCH', 'DELETE']:
            return [IsAdmin()]
        return [IsAuthenticated()]


class EquipmentListCreateView(generics.ListCreateAPIView):
    queryset = Equipment.objects.all()
    serializer_class = EquipmentSerializer
    filterset_fields = ['status', 'category', 'responsible_person']
    search_fields = ['name', 'code', 'location']

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAdmin()]
        return [IsAuthenticated(), ReadOnlyIfObserver()]


class EquipmentDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Equipment.objects.all()
    serializer_class = EquipmentSerializer

    def get_permissions(self):
        if self.request.method in ['PUT', 'PATCH', 'DELETE']:
            return [IsAdmin()]
        return [IsAuthenticated()]


class MaintenancePlanListCreateView(generics.ListCreateAPIView):
    queryset = MaintenancePlan.objects.all()
    serializer_class = MaintenancePlanSerializer
    filterset_fields = ['equipment', 'is_active']

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAdmin()]
        return [IsAuthenticated(), ReadOnlyIfObserver()]


class MaintenancePlanDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = MaintenancePlan.objects.all()
    serializer_class = MaintenancePlanSerializer

    def get_permissions(self):
        if self.request.method in ['PUT', 'PATCH', 'DELETE']:
            return [IsAdmin()]
        return [IsAuthenticated()]


class InspectionRecordListCreateView(generics.ListCreateAPIView):
    queryset = InspectionRecord.objects.all()
    serializer_class = InspectionRecordSerializer
    filterset_fields = ['equipment', 'status', 'inspector']

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAdminOrFieldStaff()]
        return [IsAuthenticated(), ReadOnlyIfObserver()]

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
        return [IsAuthenticated()]


class AlertListView(generics.ListAPIView):
    queryset = Alert.objects.all()
    serializer_class = AlertSerializer
    filterset_fields = ['equipment', 'alert_type', 'status', 'assigned_to']
    search_fields = ['title', 'description']


class AlertDetailView(generics.RetrieveAPIView):
    queryset = Alert.objects.all()
    serializer_class = AlertSerializer


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
