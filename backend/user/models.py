from django.db import models

class Admin(models.Model):
    id = models.AutoField(primary_key=True)
    username = models.CharField(max_length=50, unique=True, db_index=True)
    password = models.CharField(max_length=100)

    def __str__(self):
        return self.username


class Employee(models.Model):
    id = models.AutoField(primary_key=True)
    empid = models.CharField(max_length=50, unique=True)
    password = models.CharField(max_length=100)
    name = models.CharField(max_length=50)
    email = models.EmailField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class User(models.Model):
    id = models.AutoField(primary_key=True)
    email = models.EmailField(max_length=255, unique=True)
    hashed_password = models.CharField(max_length=255)
    is_superadmin = models.BooleanField(default=False)
    is_hr = models.BooleanField(default=False)
    is_manager = models.BooleanField(default=False)
    is_employee = models.BooleanField(default=False)

    employee = models.ForeignKey(
        Employee,
        related_name='user',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.email


class EmployeeManagerMap(models.Model):
    id = models.AutoField(primary_key=True)
    employee = models.ForeignKey(
        Employee,
        related_name='manager_mapping',
        on_delete=models.CASCADE
    )
    manager = models.ForeignKey(
        User,
        related_name='employees_managed',
        on_delete=models.CASCADE
    )

    def __str__(self):
        return f"{self.manager.email} -> {self.employee.name}"


class TimeLog(models.Model):
    ACTION_CHOICES = [
        ('IN', 'IN'),
        ('OUT', 'OUT'),
    ]

    id = models.AutoField(primary_key=True)
    employee = models.ForeignKey(Employee, related_name='logs', on_delete=models.CASCADE)
    timestamp = models.DateTimeField()
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)

    def __str__(self):
        return f"{self.employee.name} - {self.action} - {self.timestamp}"


class Environment(models.Model):
    id = models.AutoField(primary_key=True)
    key = models.CharField(max_length=50, unique=True)
    value = models.CharField(max_length=100)

    def __str__(self):
        return self.key


class MissReport(models.Model):
    id = models.AutoField(primary_key=True)
    timestamp = models.DateTimeField()
    employee = models.ForeignKey(Employee, related_name='reports', on_delete=models.CASCADE)
    action = models.CharField(max_length=10)
    reason = models.CharField(max_length=300)
    status = models.CharField(max_length=10)

    def __str__(self):
        return f"{self.employee.name} - {self.action} - {self.status}"

class SuperAdminUser(User):
    class Meta:
        proxy = True
        verbose_name = "Super Admin"
        verbose_name_plural = "Super Admins"
