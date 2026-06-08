from django.urls import path
from . import views

urlpatterns = [
    path('users/', views.UserListCreateView.as_view(), name='user-list-create'),
    path('users/<int:pk>/', views.UserDetailView.as_view(), name='user-detail'),

    path('equipments/', views.EquipmentListCreateView.as_view(), name='equipment-list-create'),
    path('equipments/<int:pk>/', views.EquipmentDetailView.as_view(), name='equipment-detail'),

    path('maintenance-plans/', views.MaintenancePlanListCreateView.as_view(), name='maintenance-plan-list-create'),
    path('maintenance-plans/<int:pk>/', views.MaintenancePlanDetailView.as_view(), name='maintenance-plan-detail'),

    path('inspections/', views.InspectionRecordListCreateView.as_view(), name='inspection-list-create'),
    path('inspections/<int:pk>/', views.InspectionRecordDetailView.as_view(), name='inspection-detail'),

    path('alerts/', views.AlertListView.as_view(), name='alert-list'),
    path('alerts/<int:pk>/', views.AlertDetailView.as_view(), name='alert-detail'),
    path('alerts/<int:pk>/close-request/', views.AlertCloseRequestView.as_view(), name='alert-close-request'),
    path('alerts/<int:pk>/confirm-close/', views.AlertConfirmCloseView.as_view(), name='alert-confirm-close'),
    path('alerts/run-checks/', views.AlertRunChecksView.as_view(), name='alert-run-checks'),

    path('repair-orders/', views.RepairOrderListCreateView.as_view(), name='repair-order-list-create'),
    path('repair-orders/<int:pk>/', views.RepairOrderDetailView.as_view(), name='repair-order-detail'),
    path('repair-orders/<int:pk>/submit-progress/', views.RepairOrderSubmitProgressView.as_view(), name='repair-order-submit-progress'),
    path('repair-orders/<int:pk>/completion-request/', views.RepairOrderCompletionRequestView.as_view(), name='repair-order-completion-request'),
    path('repair-orders/<int:pk>/confirm-close/', views.RepairOrderConfirmCloseView.as_view(), name='repair-order-confirm-close'),

    path('stats/by-equipment/', views.StatsByEquipmentView.as_view(), name='stats-by-equipment'),
    path('stats/by-person/', views.StatsByResponsiblePersonView.as_view(), name='stats-by-person'),

    path('stats/repair/by-equipment/', views.RepairStatsByEquipmentView.as_view(), name='repair-stats-by-equipment'),
    path('stats/repair/by-handler/', views.RepairStatsByHandlerView.as_view(), name='repair-stats-by-handler'),
    path('stats/repair/by-fault-type/', views.RepairStatsByFaultTypeView.as_view(), name='repair-stats-by-fault-type'),
    path('stats/repair/by-status/', views.RepairStatsByStatusView.as_view(), name='repair-stats-by-status'),

    path('export/alerts/', views.ExportAlertsCsvView.as_view(), name='export-alerts'),
    path('export/stats-by-equipment/', views.ExportStatsByEquipmentCsvView.as_view(), name='export-stats-by-equipment'),
    path('export/stats-by-person/', views.ExportStatsByPersonCsvView.as_view(), name='export-stats-by-person'),

    path('export/repair-orders/', views.ExportRepairOrdersCsvView.as_view(), name='export-repair-orders'),
    path('export/repair-stats/', views.ExportRepairStatsCsvView.as_view(), name='export-repair-stats'),
]
