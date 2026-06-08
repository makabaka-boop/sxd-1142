from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ROLE_ADMIN = 'admin'
    ROLE_FIELD_STAFF = 'field_staff'
    ROLE_OBSERVER = 'observer'
    ROLE_CHOICES = [
        (ROLE_ADMIN, '管理员'),
        (ROLE_FIELD_STAFF, '现场人员'),
        (ROLE_OBSERVER, '观察员'),
    ]
    role = models.CharField('角色', max_length=20, choices=ROLE_CHOICES, default=ROLE_OBSERVER)
    phone = models.CharField('手机号', max_length=20, blank=True, default='')

    class Meta:
        verbose_name = '用户'
        verbose_name_plural = '用户'

    @property
    def is_admin(self):
        return self.role == self.ROLE_ADMIN

    @property
    def is_field_staff(self):
        return self.role == self.ROLE_FIELD_STAFF

    @property
    def is_observer(self):
        return self.role == self.ROLE_OBSERVER


class Equipment(models.Model):
    STATUS_NORMAL = 'normal'
    STATUS_UNDER_REPAIR = 'under_repair'
    STATUS_RETIRED = 'retired'
    STATUS_CHOICES = [
        (STATUS_NORMAL, '正常'),
        (STATUS_UNDER_REPAIR, '维修中'),
        (STATUS_RETIRED, '已退役'),
    ]
    CATEGORY_CARDIO = 'cardio'
    CATEGORY_STRENGTH = 'strength'
    CATEGORY_FLEXIBILITY = 'flexibility'
    CATEGORY_OTHER = 'other'
    CATEGORY_CHOICES = [
        (CATEGORY_CARDIO, '有氧'),
        (CATEGORY_STRENGTH, '力量'),
        (CATEGORY_FLEXIBILITY, '柔韧'),
        (CATEGORY_OTHER, '其他'),
    ]
    name = models.CharField('器械名称', max_length=100)
    code = models.CharField('器械编号', max_length=50, unique=True)
    category = models.CharField('分类', max_length=20, choices=CATEGORY_CHOICES, default=CATEGORY_OTHER)
    location = models.CharField('存放位置', max_length=200, blank=True, default='')
    purchase_date = models.DateField('购入日期', null=True, blank=True)
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default=STATUS_NORMAL)
    responsible_person = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='equipments', verbose_name='责任人'
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '器械'
        verbose_name_plural = '器械'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.code} - {self.name}'


class MaintenancePlan(models.Model):
    equipment = models.ForeignKey(
        Equipment, on_delete=models.CASCADE,
        related_name='maintenance_plans', verbose_name='器械'
    )
    cycle_days = models.PositiveIntegerField('保养周期(天)')
    last_maintenance_date = models.DateField('上次保养日期', null=True, blank=True)
    next_maintenance_date = models.DateField('下次保养日期')
    description = models.TextField('保养说明', blank=True, default='')
    is_active = models.BooleanField('是否启用', default=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '保养计划'
        verbose_name_plural = '保养计划'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.equipment.name} - 每{self.cycle_days}天保养'


class InspectionRecord(models.Model):
    STATUS_NORMAL = 'normal'
    STATUS_ABNORMAL = 'abnormal'
    STATUS_CHOICES = [
        (STATUS_NORMAL, '正常'),
        (STATUS_ABNORMAL, '异常'),
    ]
    equipment = models.ForeignKey(
        Equipment, on_delete=models.CASCADE,
        related_name='inspection_records', verbose_name='器械'
    )
    inspector = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='inspection_records', verbose_name='巡查人'
    )
    inspection_date = models.DateTimeField('巡查时间', auto_now_add=True)
    status = models.CharField('巡查状态', max_length=20, choices=STATUS_CHOICES, default=STATUS_NORMAL)
    issue_description = models.TextField('问题描述', blank=True, default='')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '巡查记录'
        verbose_name_plural = '巡查记录'
        ordering = ['-inspection_date']

    def __str__(self):
        return f'{self.equipment.name} - {self.get_status_display()} - {self.inspection_date}'


class Alert(models.Model):
    TYPE_CYCLE = 'cycle'
    TYPE_CONSECUTIVE_ANOMALY = 'consecutive_anomaly'
    TYPE_TIMEOUT = 'timeout'
    TYPE_DUPLICATE_REPAIR = 'duplicate_repair'
    TYPE_CHOICES = [
        (TYPE_CYCLE, '保养周期'),
        (TYPE_CONSECUTIVE_ANOMALY, '连续异常'),
        (TYPE_TIMEOUT, '处理超时'),
        (TYPE_DUPLICATE_REPAIR, '重复报修'),
    ]
    STATUS_OPEN = 'open'
    STATUS_PROCESSING = 'processing'
    STATUS_CLOSED = 'closed'
    STATUS_CHOICES = [
        (STATUS_OPEN, '待处理'),
        (STATUS_PROCESSING, '处理中'),
        (STATUS_CLOSED, '已关闭'),
    ]
    equipment = models.ForeignKey(
        Equipment, on_delete=models.CASCADE,
        related_name='alerts', verbose_name='器械'
    )
    alert_type = models.CharField('提醒类型', max_length=30, choices=TYPE_CHOICES)
    title = models.CharField('提醒标题', max_length=200)
    description = models.TextField('提醒描述', blank=True, default='')
    issue_key = models.CharField('问题标识(去重用)', max_length=255, db_index=True)
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN, db_index=True)
    assigned_to = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_alerts', verbose_name='指派处理人'
    )
    close_request_note = models.TextField('关闭申请说明', blank=True, default='')
    close_requested_at = models.DateTimeField('关闭申请时间', null=True, blank=True)
    close_requested_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='close_requested_alerts', verbose_name='关闭申请人'
    )
    confirmed_at = models.DateTimeField('确认关闭时间', null=True, blank=True)
    confirmed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='confirmed_alerts', verbose_name='确认关闭人'
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '提醒'
        verbose_name_plural = '提醒'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.equipment.name} - {self.get_alert_type_display()} - {self.get_status_display()}'
