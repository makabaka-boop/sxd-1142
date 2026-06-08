from django.contrib import admin
from .models import Alert, Equipment, InspectionRecord, MaintenancePlan, User


admin.site.register(User)
admin.site.register(Equipment)
admin.site.register(MaintenancePlan)
admin.site.register(InspectionRecord)
admin.site.register(Alert)
