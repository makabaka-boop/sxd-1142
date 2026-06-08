import csv
from django.db.models import Count, Q
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import generics, status, views
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .alert_engine import run_all_checks
from .models import Alert, Equipment, InspectionRecord, MaintenancePlan, RepairOrder, RepairProgress, User
from .permissions import IsAdmin, IsAdminOrFieldStaff, IsAdminOrObserver, IsNotObserver
from .serializers import (
    AlertCloseRequestSerializer,
    AlertConfirmCloseSerializer,
    AlertSerializer,
    EquipmentSerializer,
    InspectionRecordSerializer,
    MaintenancePlanSerializer,
    RepairOrderCompletionRequestSerializer,
    RepairOrderConfirmCloseSerializer,
    RepairOrderCreateSerializer,
    RepairOrderSerializer,
    RepairOrderUpdateSerializer,
    RepairProgressSerializer,
    RepairProgressSubmitSerializer,
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


class RepairOrderListCreateView(generics.ListCreateAPIView):
    queryset = RepairOrder.objects.select_related(
        'equipment', 'handler', 'created_by', 'inspection_record', 'alert', 'confirmed_by'
    ).prefetch_related('progresses').all()

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return RepairOrderCreateSerializer
        return RepairOrderSerializer

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAdminOrFieldStaff()]
        return [IsAuthenticated()]

    filterset_fields = ['equipment', 'handler', 'status', 'priority', 'fault_type']
    search_fields = ['fault_description', 'equipment__name', 'equipment__code']

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.is_admin:
            pass
        elif user.is_field_staff:
            queryset = queryset.filter(handler=user)
        elif user.is_observer:
            pass
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        return queryset

    def perform_create(self, serializer):
        order = serializer.save(created_by=self.request.user)
        if order.alert:
            order.alert.status = Alert.STATUS_PROCESSING
            order.alert.save()
        if order.equipment.status != Equipment.STATUS_UNDER_REPAIR:
            order.equipment.status = Equipment.STATUS_UNDER_REPAIR
            order.equipment.save()
        if order.handler and order.status == RepairOrder.STATUS_PENDING:
            order.status = RepairOrder.STATUS_IN_PROGRESS
            order.save()


class RepairOrderDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = RepairOrder.objects.select_related(
        'equipment', 'handler', 'created_by', 'inspection_record', 'alert', 'confirmed_by'
    ).prefetch_related('progresses').all()

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return RepairOrderUpdateSerializer
        return RepairOrderSerializer

    def get_permissions(self):
        if self.request.method in ['PUT', 'PATCH']:
            return [IsAdmin()]
        if self.request.method == 'DELETE':
            return [IsAdmin()]
        return [IsAuthenticated()]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.is_admin:
            pass
        elif user.is_field_staff:
            queryset = queryset.filter(handler=user)
        return queryset


class RepairOrderSubmitProgressView(views.APIView):
    permission_classes = [IsAdminOrFieldStaff]

    def post(self, request, pk):
        try:
            order = RepairOrder.objects.get(pk=pk)
        except RepairOrder.DoesNotExist:
            return Response({'detail': '维修工单不存在'}, status=status.HTTP_404_NOT_FOUND)

        if request.user.is_field_staff and order.handler_id != request.user.id:
            return Response({'detail': '无权操作此工单'}, status=status.HTTP_403_FORBIDDEN)

        if order.status == RepairOrder.STATUS_CLOSED:
            return Response({'detail': '工单已关闭，无法提交进展'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = RepairProgressSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if order.status == RepairOrder.STATUS_PENDING:
            order.status = RepairOrder.STATUS_IN_PROGRESS
            order.save()

        progress = RepairProgress.objects.create(
            repair_order=order,
            submitter=request.user,
            content=serializer.validated_data['content'],
        )
        return Response(RepairProgressSerializer(progress).data, status=status.HTTP_201_CREATED)


class RepairOrderCompletionRequestView(views.APIView):
    permission_classes = [IsAdminOrFieldStaff]

    def post(self, request, pk):
        try:
            order = RepairOrder.objects.get(pk=pk)
        except RepairOrder.DoesNotExist:
            return Response({'detail': '维修工单不存在'}, status=status.HTTP_404_NOT_FOUND)

        if request.user.is_field_staff and order.handler_id != request.user.id:
            return Response({'detail': '无权操作此工单'}, status=status.HTTP_403_FORBIDDEN)

        if order.status == RepairOrder.STATUS_CLOSED:
            return Response({'detail': '工单已关闭'}, status=status.HTTP_400_BAD_REQUEST)

        if order.status == RepairOrder.STATUS_COMPLETION_REQUESTED:
            return Response({'detail': '已提交完成申请，等待管理员确认'}, status=status.HTTP_400_BAD_REQUEST)

        if order.status == RepairOrder.STATUS_PENDING:
            return Response({'detail': '工单尚未开始处理'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = RepairOrderCompletionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order.status = RepairOrder.STATUS_COMPLETION_REQUESTED
        order.completion_note = serializer.validated_data['completion_note']
        order.completion_time = timezone.now()
        order.save()

        return Response(RepairOrderSerializer(order).data)


class RepairOrderConfirmCloseView(views.APIView):
    permission_classes = [IsAdmin]

    def post(self, request, pk):
        try:
            order = RepairOrder.objects.get(pk=pk)
        except RepairOrder.DoesNotExist:
            return Response({'detail': '维修工单不存在'}, status=status.HTTP_404_NOT_FOUND)

        if order.status == RepairOrder.STATUS_CLOSED:
            return Response({'detail': '工单已关闭'}, status=status.HTTP_400_BAD_REQUEST)

        if order.status != RepairOrder.STATUS_COMPLETION_REQUESTED:
            return Response({'detail': '工单尚未提交完成申请'}, status=status.HTTP_400_BAD_REQUEST)

        order.status = RepairOrder.STATUS_CLOSED
        order.confirmed_by = request.user
        order.confirmed_at = timezone.now()
        order.save()

        if order.equipment.status == Equipment.STATUS_UNDER_REPAIR:
            order.equipment.status = Equipment.STATUS_NORMAL
            order.equipment.save()

        if order.alert and order.alert.status != Alert.STATUS_CLOSED:
            order.alert.status = Alert.STATUS_CLOSED
            order.alert.confirmed_at = timezone.now()
            order.alert.confirmed_by = request.user
            order.alert.save()

        if order.inspection_record and order.inspection_record.status == InspectionRecord.STATUS_ABNORMAL:
            active_repairs = RepairOrder.objects.filter(
                inspection_record=order.inspection_record
            ).exclude(status=RepairOrder.STATUS_CLOSED).exclude(pk=order.pk)
            if not active_repairs.exists():
                order.inspection_record.status = InspectionRecord.STATUS_NORMAL
                order.inspection_record.save()

        if order.equipment.maintenance_plans.filter(is_active=True).exists():
            plan = order.equipment.maintenance_plans.filter(is_active=True).first()
            plan.last_maintenance_date = timezone.now().date()
            from datetime import timedelta
            plan.next_maintenance_date = plan.last_maintenance_date + timedelta(days=plan.cycle_days)
            plan.save()

        return Response(RepairOrderSerializer(order).data)


class RepairStatsByEquipmentView(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = RepairOrder.objects.all()
        equipment_id = request.query_params.get('equipment')
        if equipment_id:
            queryset = queryset.filter(equipment_id=equipment_id)

        stats = queryset.values(
            'equipment__id', 'equipment__name', 'equipment__code'
        ).annotate(
            total=Count('id'),
            pending_count=Count('id', filter=Q(status=RepairOrder.STATUS_PENDING)),
            in_progress_count=Count('id', filter=Q(status=RepairOrder.STATUS_IN_PROGRESS)),
            completion_requested_count=Count('id', filter=Q(status=RepairOrder.STATUS_COMPLETION_REQUESTED)),
            closed_count=Count('id', filter=Q(status=RepairOrder.STATUS_CLOSED)),
        ).order_by('-total')

        return Response(list(stats))


class RepairStatsByHandlerView(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = RepairOrder.objects.all()
        user_id = request.query_params.get('user')
        if user_id:
            queryset = queryset.filter(handler_id=user_id)

        stats = queryset.values(
            'handler__id', 'handler__username'
        ).annotate(
            total=Count('id'),
            pending_count=Count('id', filter=Q(status=RepairOrder.STATUS_PENDING)),
            in_progress_count=Count('id', filter=Q(status=RepairOrder.STATUS_IN_PROGRESS)),
            completion_requested_count=Count('id', filter=Q(status=RepairOrder.STATUS_COMPLETION_REQUESTED)),
            closed_count=Count('id', filter=Q(status=RepairOrder.STATUS_CLOSED)),
        ).order_by('-total')

        return Response(list(stats))


class RepairStatsByFaultTypeView(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = RepairOrder.objects.all()
        fault_type = request.query_params.get('fault_type')
        if fault_type:
            queryset = queryset.filter(fault_type=fault_type)

        stats = queryset.values('fault_type').annotate(
            total=Count('id'),
            pending_count=Count('id', filter=Q(status=RepairOrder.STATUS_PENDING)),
            in_progress_count=Count('id', filter=Q(status=RepairOrder.STATUS_IN_PROGRESS)),
            completion_requested_count=Count('id', filter=Q(status=RepairOrder.STATUS_COMPLETION_REQUESTED)),
            closed_count=Count('id', filter=Q(status=RepairOrder.STATUS_CLOSED)),
        ).order_by('-total')

        return Response(list(stats))


class RepairStatsByStatusView(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = RepairOrder.objects.all()
        equipment_id = request.query_params.get('equipment')
        handler_id = request.query_params.get('handler')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        if equipment_id:
            queryset = queryset.filter(equipment_id=equipment_id)
        if handler_id:
            queryset = queryset.filter(handler_id=handler_id)
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)

        stats = queryset.values('status').annotate(
            count=Count('id'),
        ).order_by('status')

        return Response(list(stats))


class ExportRepairOrdersCsvView(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = RepairOrder.objects.select_related(
            'equipment', 'handler', 'created_by', 'inspection_record', 'alert', 'confirmed_by'
        ).all()
        equipment_id = request.query_params.get('equipment')
        handler_id = request.query_params.get('handler')
        order_status = request.query_params.get('status')
        priority = request.query_params.get('priority')
        fault_type = request.query_params.get('fault_type')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        if equipment_id:
            queryset = queryset.filter(equipment_id=equipment_id)
        if handler_id:
            queryset = queryset.filter(handler_id=handler_id)
        if order_status:
            queryset = queryset.filter(status=order_status)
        if priority:
            queryset = queryset.filter(priority=priority)
        if fault_type:
            queryset = queryset.filter(fault_type=fault_type)
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="repair_orders_export.csv"'
        writer = csv.writer(response)
        writer.writerow([
            'ID', '器械编号', '器械名称', '故障类型', '故障描述', '优先级',
            '期望完成时间', '处理人', '工单状态', '处理说明', '完成说明',
            '完成时间', '创建人', '确认关闭人', '确认关闭时间', '关联提醒ID', '关联巡查记录ID', '创建时间',
        ])
        for order in queryset:
            writer.writerow([
                order.id,
                order.equipment.code,
                order.equipment.name,
                order.get_fault_type_display(),
                order.fault_description,
                order.get_priority_display(),
                order.expected_completion_time.strftime('%Y-%m-%d %H:%M:%S') if order.expected_completion_time else '',
                order.handler.username if order.handler else '',
                order.get_status_display(),
                order.processing_note,
                order.completion_note,
                order.completion_time.strftime('%Y-%m-%d %H:%M:%S') if order.completion_time else '',
                order.created_by.username if order.created_by else '',
                order.confirmed_by.username if order.confirmed_by else '',
                order.confirmed_at.strftime('%Y-%m-%d %H:%M:%S') if order.confirmed_at else '',
                order.alert_id or '',
                order.inspection_record_id or '',
                order.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            ])
        return response


class ExportRepairStatsCsvView(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        group_by = request.query_params.get('group_by', 'equipment')
        queryset = RepairOrder.objects.all()
        equipment_id = request.query_params.get('equipment')
        handler_id = request.query_params.get('handler')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        if equipment_id:
            queryset = queryset.filter(equipment_id=equipment_id)
        if handler_id:
            queryset = queryset.filter(handler_id=handler_id)
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)

        if group_by == 'handler':
            stats = queryset.values(
                'handler__id', 'handler__username'
            ).annotate(
                total=Count('id'),
                pending_count=Count('id', filter=Q(status=RepairOrder.STATUS_PENDING)),
                in_progress_count=Count('id', filter=Q(status=RepairOrder.STATUS_IN_PROGRESS)),
                completion_requested_count=Count('id', filter=Q(status=RepairOrder.STATUS_COMPLETION_REQUESTED)),
                closed_count=Count('id', filter=Q(status=RepairOrder.STATUS_CLOSED)),
            ).order_by('-total')
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="repair_stats_by_handler.csv"'
            writer = csv.writer(response)
            writer.writerow(['处理人ID', '处理人用户名', '总数', '待处理', '处理中', '申请完成', '已关闭'])
            for row in stats:
                writer.writerow([
                    row['handler__id'] or '',
                    row['handler__username'] or '(未指派)',
                    row['total'],
                    row['pending_count'],
                    row['in_progress_count'],
                    row['completion_requested_count'],
                    row['closed_count'],
                ])
        elif group_by == 'fault_type':
            stats = queryset.values('fault_type').annotate(
                total=Count('id'),
                pending_count=Count('id', filter=Q(status=RepairOrder.STATUS_PENDING)),
                in_progress_count=Count('id', filter=Q(status=RepairOrder.STATUS_IN_PROGRESS)),
                completion_requested_count=Count('id', filter=Q(status=RepairOrder.STATUS_COMPLETION_REQUESTED)),
                closed_count=Count('id', filter=Q(status=RepairOrder.STATUS_CLOSED)),
            ).order_by('-total')
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="repair_stats_by_fault_type.csv"'
            writer = csv.writer(response)
            writer.writerow(['故障类型', '总数', '待处理', '处理中', '申请完成', '已关闭'])
            fault_display = dict(RepairOrder.FAULT_TYPE_CHOICES)
            for row in stats:
                writer.writerow([
                    fault_display.get(row['fault_type'], row['fault_type']),
                    row['total'],
                    row['pending_count'],
                    row['in_progress_count'],
                    row['completion_requested_count'],
                    row['closed_count'],
                ])
        else:
            stats = queryset.values(
                'equipment__id', 'equipment__name', 'equipment__code'
            ).annotate(
                total=Count('id'),
                pending_count=Count('id', filter=Q(status=RepairOrder.STATUS_PENDING)),
                in_progress_count=Count('id', filter=Q(status=RepairOrder.STATUS_IN_PROGRESS)),
                completion_requested_count=Count('id', filter=Q(status=RepairOrder.STATUS_COMPLETION_REQUESTED)),
                closed_count=Count('id', filter=Q(status=RepairOrder.STATUS_CLOSED)),
            ).order_by('-total')
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="repair_stats_by_equipment.csv"'
            writer = csv.writer(response)
            writer.writerow(['器械ID', '器械编号', '器械名称', '总数', '待处理', '处理中', '申请完成', '已关闭'])
            for row in stats:
                writer.writerow([
                    row['equipment__id'],
                    row['equipment__code'],
                    row['equipment__name'],
                    row['total'],
                    row['pending_count'],
                    row['in_progress_count'],
                    row['completion_requested_count'],
                    row['closed_count'],
                ])
        return response
