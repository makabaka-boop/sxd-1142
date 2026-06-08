from rest_framework import serializers
from .models import User, Equipment, MaintenancePlan, InspectionRecord, Alert, RepairOrder, RepairProgress


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'role', 'phone', 'email', 'first_name', 'last_name']
        read_only_fields = ['id']
        extra_kwargs = {'password': {'write_only': True}}


class UserCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'password', 'role', 'phone', 'email', 'first_name', 'last_name']
        extra_kwargs = {'password': {'write_only': True, 'required': True}}

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class EquipmentSerializer(serializers.ModelSerializer):
    responsible_person_name = serializers.CharField(source='responsible_person.username', read_only=True, default=None)

    class Meta:
        model = Equipment
        fields = [
            'id', 'name', 'code', 'category', 'location', 'purchase_date',
            'status', 'responsible_person', 'responsible_person_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class MaintenancePlanSerializer(serializers.ModelSerializer):
    equipment_name = serializers.CharField(source='equipment.name', read_only=True)

    class Meta:
        model = MaintenancePlan
        fields = [
            'id', 'equipment', 'equipment_name', 'cycle_days',
            'last_maintenance_date', 'next_maintenance_date',
            'description', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class InspectionRecordSerializer(serializers.ModelSerializer):
    inspector_name = serializers.CharField(source='inspector.username', read_only=True, default=None)
    equipment_name = serializers.CharField(source='equipment.name', read_only=True)

    class Meta:
        model = InspectionRecord
        fields = [
            'id', 'equipment', 'equipment_name', 'inspector', 'inspector_name',
            'inspection_date', 'status', 'issue_description',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'inspection_date', 'created_at', 'updated_at']


class AlertSerializer(serializers.ModelSerializer):
    equipment_name = serializers.CharField(source='equipment.name', read_only=True)
    equipment_code = serializers.CharField(source='equipment.code', read_only=True)
    assigned_to_name = serializers.CharField(source='assigned_to.username', read_only=True, default=None)
    close_requested_by_name = serializers.CharField(source='close_requested_by.username', read_only=True, default=None)
    confirmed_by_name = serializers.CharField(source='confirmed_by.username', read_only=True, default=None)
    alert_type_display = serializers.CharField(source='get_alert_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Alert
        fields = [
            'id', 'equipment', 'equipment_name', 'equipment_code',
            'alert_type', 'alert_type_display', 'title', 'description',
            'issue_key', 'status', 'status_display',
            'assigned_to', 'assigned_to_name',
            'close_request_note', 'close_requested_at', 'close_requested_by', 'close_requested_by_name',
            'confirmed_at', 'confirmed_by', 'confirmed_by_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'issue_key', 'status', 'close_requested_at', 'close_requested_by',
            'confirmed_at', 'confirmed_by', 'created_at', 'updated_at'
        ]


class AlertCloseRequestSerializer(serializers.Serializer):
    close_request_note = serializers.CharField(required=True, min_length=1)


class AlertConfirmCloseSerializer(serializers.Serializer):
    pass


class RepairProgressSerializer(serializers.ModelSerializer):
    submitter_name = serializers.CharField(source='submitter.username', read_only=True, default=None)

    class Meta:
        model = RepairProgress
        fields = ['id', 'repair_order', 'submitter', 'submitter_name', 'content', 'created_at']
        read_only_fields = ['id', 'created_at']


class RepairOrderSerializer(serializers.ModelSerializer):
    equipment_name = serializers.CharField(source='equipment.name', read_only=True)
    equipment_code = serializers.CharField(source='equipment.code', read_only=True)
    handler_name = serializers.CharField(source='handler.username', read_only=True, default=None)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True, default=None)
    confirmed_by_name = serializers.CharField(source='confirmed_by.username', read_only=True, default=None)
    fault_type_display = serializers.CharField(source='get_fault_type_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    alert_title = serializers.CharField(source='alert.title', read_only=True, default=None)
    progresses = RepairProgressSerializer(many=True, read_only=True)

    class Meta:
        model = RepairOrder
        fields = [
            'id', 'equipment', 'equipment_name', 'equipment_code',
            'inspection_record', 'alert', 'alert_title',
            'fault_type', 'fault_type_display', 'fault_description',
            'priority', 'priority_display', 'expected_completion_time',
            'handler', 'handler_name', 'status', 'status_display',
            'processing_note', 'completion_note', 'completion_time',
            'created_by', 'created_by_name',
            'confirmed_by', 'confirmed_by_name', 'confirmed_at',
            'created_at', 'updated_at', 'progresses',
        ]
        read_only_fields = [
            'id', 'status', 'completion_note', 'completion_time',
            'confirmed_by', 'confirmed_at', 'created_at', 'updated_at',
        ]


class RepairOrderCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RepairOrder
        fields = [
            'id', 'equipment', 'inspection_record', 'alert',
            'fault_type', 'fault_description', 'priority',
            'expected_completion_time', 'handler',
        ]
        read_only_fields = ['id']

    def validate_inspection_record(self, value):
        if value and value.status != InspectionRecord.STATUS_ABNORMAL:
            raise serializers.ValidationError('只能关联异常巡查记录')
        return value

    def validate_alert(self, value):
        if value and value.status == Alert.STATUS_CLOSED:
            raise serializers.ValidationError('不能关联已关闭的提醒')
        return value


class RepairProgressSubmitSerializer(serializers.Serializer):
    content = serializers.CharField(required=True, min_length=1)


class RepairOrderCompletionRequestSerializer(serializers.Serializer):
    completion_note = serializers.CharField(required=True, min_length=1)


class RepairOrderConfirmCloseSerializer(serializers.Serializer):
    pass
