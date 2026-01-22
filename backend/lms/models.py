from django.db import models
from user.models import Employee, User

class LeaveRequest(models.Model):
    id = models.AutoField(primary_key=True)

    employee = models.ForeignKey(
        Employee,
        related_name="leaves",
        on_delete=models.CASCADE
    )

    leave_type = models.CharField(max_length=20)
    apply_date = models.DateTimeField(auto_now_add=True)

    start_date = models.DateField()
    end_date = models.DateField()

    total_days = models.DecimalField(max_digits=4, decimal_places=1, default=0)
    leave_without_pay = models.DecimalField(max_digits=4, decimal_places=1, default=0)

    reason = models.TextField(null=True, blank=True)
    attachment = models.CharField(max_length=255, null=True, blank=True)

    status = models.CharField(
        max_length=20,
        default="pending"
    )  # pending, approved, rejected

    half_day_start_type = models.CharField(max_length=20, null=True, blank=True)
    half_day_end_type = models.CharField(max_length=10, null=True, blank=True)

    approve_date = models.DateField(null=True, blank=True)
    approve_comment = models.TextField(null=True, blank=True)

    reject_date = models.DateField(null=True, blank=True)
    reject_comment = models.TextField(null=True, blank=True)

    action_by = models.ForeignKey(
        User,
        related_name="leave_actions",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    casual_deducted = models.DecimalField(max_digits=4, decimal_places=1, default=0)
    earned_deducted = models.DecimalField(max_digits=4, decimal_places=1, default=0)
    sick_deducted = models.DecimalField(max_digits=4, decimal_places=1, default=0)
    optional_deducted = models.DecimalField(max_digits=4, decimal_places=1, default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "leave_requests"

class LeaveBalance(models.Model):
    id = models.AutoField(primary_key=True)

    employee = models.ForeignKey(
        Employee,
        related_name="leave_balances",
        on_delete=models.CASCADE
    )

    sick_leave = models.FloatField(default=0)
    casual_leave = models.FloatField(default=0)
    optional_leave = models.FloatField(default=0)
    earned_leave = models.FloatField(default=0)

    total_sick_leave = models.FloatField(default=0)
    total_casual_leave = models.FloatField(default=0)
    total_optional_leave = models.FloatField(default=0)
    total_earned_leave = models.FloatField(default=0)

    updated_by = models.ForeignKey(
        User,
        related_name="leave_updated_by",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "leave_balances"

class Holiday(models.Model):
    id = models.AutoField(primary_key=True)

    festival_date = models.DateField(unique=True)
    festival_name = models.CharField(max_length=100)

    created_by = models.ForeignKey(
        User,
        related_name="holiday_created",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    updated_by = models.ForeignKey(
        User,
        related_name="holiday_updated",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "holiday_calendar"
        ordering = ["festival_date"]
