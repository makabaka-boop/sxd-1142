import hashlib
from datetime import timedelta

from django.conf import settings
from django.db.models import Count
from django.utils import timezone

from .models import Alert, Equipment, InspectionRecord, MaintenancePlan


def _make_issue_key(equipment_id, alert_type, extra=''):
    raw = f'{equipment_id}:{alert_type}:{extra.strip().lower()}'
    return hashlib.md5(raw.encode('utf-8')).hexdigest()


def _create_alert_if_not_exists(equipment_id, alert_type, title, description='', issue_key_extra='', assigned_to=None):
    issue_key = _make_issue_key(equipment_id, alert_type, issue_key_extra)
    existing = Alert.objects.filter(issue_key=issue_key).exclude(status=Alert.STATUS_CLOSED).first()
    if existing:
        return existing, False
    alert = Alert.objects.create(
        equipment_id=equipment_id,
        alert_type=alert_type,
        title=title,
        description=description,
        issue_key=issue_key,
        assigned_to=assigned_to,
    )
    return alert, True


def check_maintenance_cycle():
    today = timezone.now().date()
    plans = MaintenancePlan.objects.filter(
        is_active=True,
        next_maintenance_date__lte=today,
    )
    created = []
    for plan in plans:
        equip = plan.equipment
        if equip.status == Equipment.STATUS_RETIRED:
            continue
        title = f'保养到期: {equip.name}'
        desc = f'{equip.name}(编号{equip.code}) 保养已到期，计划周期{plan.cycle_days}天，上次保养日期{plan.last_maintenance_date or "无记录"}'
        alert, created_flag = _create_alert_if_not_exists(
            equipment_id=equip.id,
            alert_type=Alert.TYPE_CYCLE,
            title=title,
            description=desc,
            issue_key_extra=str(equip.id),
            assigned_to=equip.responsible_person,
        )
        if created_flag:
            created.append(alert)
    return created


def check_consecutive_anomaly():
    threshold = getattr(settings, 'CONSECUTIVE_ANOMALY_THRESHOLD', 2)
    equipments = Equipment.objects.filter(status=Equipment.STATUS_NORMAL)
    created = []
    for equip in equipments:
        records = InspectionRecord.objects.filter(
            equipment=equip
        ).order_by('-inspection_date')[:threshold]
        if len(records) < threshold:
            continue
        if all(r.status == InspectionRecord.STATUS_ABNORMAL for r in records):
            issue_desc = records[0].issue_description or '连续巡查异常'
            title = f'连续异常: {equip.name}'
            desc = f'{equip.name}(编号{equip.code}) 连续{threshold}次巡查异常，最近问题: {issue_desc}'
            alert, created_flag = _create_alert_if_not_exists(
                equipment_id=equip.id,
                alert_type=Alert.TYPE_CONSECUTIVE_ANOMALY,
                title=title,
                description=desc,
                issue_key_extra=str(equip.id),
                assigned_to=equip.responsible_person,
            )
            if created_flag:
                created.append(alert)
    return created


def check_timeout():
    timeout_days = getattr(settings, 'ALERT_TIMEOUT_DAYS', 3)
    threshold_time = timezone.now() - timedelta(days=timeout_days)
    open_alerts = Alert.objects.filter(
        status=Alert.STATUS_OPEN,
        created_at__lte=threshold_time,
    ).exclude(alert_type=Alert.TYPE_TIMEOUT)
    created = []
    for alert in open_alerts:
        title = f'处理超时: {alert.equipment.name} - {alert.get_alert_type_display()}'
        desc = f'{alert.equipment.name}(编号{alert.equipment.code}) 提醒已超过{timeout_days}天未处理，原始提醒: {alert.title}'
        alert_record, created_flag = _create_alert_if_not_exists(
            equipment_id=alert.equipment.id,
            alert_type=Alert.TYPE_TIMEOUT,
            title=title,
            description=desc,
            issue_key_extra=str(alert.equipment.id),
            assigned_to=alert.equipment.responsible_person,
        )
        if created_flag:
            created.append(alert_record)
    return created


def check_duplicate_repair():
    created = []
    recent_cutoff = timezone.now() - timedelta(days=30)
    equipments = Equipment.objects.all()
    for equip in equipments:
        abnormal_records = InspectionRecord.objects.filter(
            equipment=equip,
            status=InspectionRecord.STATUS_ABNORMAL,
            inspection_date__gte=recent_cutoff,
        ).values('issue_description').annotate(
            count=Count('id')
        ).filter(count__gte=2)
        for record in abnormal_records:
            issue_desc = record['issue_description'] or '未描述问题'
            title = f'重复报修: {equip.name}'
            desc = f'{equip.name}(编号{equip.code}) 近30天内同一问题"{issue_desc}"报修{record["count"]}次'
            alert, created_flag = _create_alert_if_not_exists(
                equipment_id=equip.id,
                alert_type=Alert.TYPE_DUPLICATE_REPAIR,
                title=title,
                description=desc,
                issue_key_extra=f'{equip.id}:{issue_desc}',
                assigned_to=equip.responsible_person,
            )
            if created_flag:
                created.append(alert)
    return created


def run_all_checks():
    results = []
    results.extend(check_maintenance_cycle())
    results.extend(check_consecutive_anomaly())
    results.extend(check_timeout())
    results.extend(check_duplicate_repair())
    return results
