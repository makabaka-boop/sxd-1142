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

    path('stats/by-equipment/', views.StatsByEquipmentView.as_view(), name='stats-by-equipment'),
    path('stats/by-person/', views.StatsByResponsiblePersonView.as_view(), name='stats-by-person'),
]
