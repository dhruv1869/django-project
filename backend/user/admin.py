from django.contrib import admin
from django.contrib.auth.hashers import make_password
from .models import User, Employee, EmployeeManagerMap, TimeLog, Environment, MissReport,SuperAdminUser
import random
import string

class SuperAdminAdmin(admin.ModelAdmin):
    list_display = ("email", "is_superadmin")
    search_fields = ("email",)

    fieldsets = (
        ("Login Info", {
            "fields": ("email",)
        }),
    )

    def get_queryset(self, request):
        """Only show superadmins"""
        qs = super().get_queryset(request)
        return qs.filter(is_superadmin=True)

    def save_model(self, request, obj, form, change):
        """Force superadmin role + auto password"""
        obj.is_superadmin = True
        obj.is_hr = False
        obj.is_manager = False
        obj.is_employee = False

        if not obj.hashed_password:
            password = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
            obj.hashed_password = make_password(password)
            print(f"SuperAdmin Password for {obj.email}: {password}")

        super().save_model(request, obj, form, change)

class UserAdmin(admin.ModelAdmin):
    list_display = ("email", "is_superadmin", "is_hr", "is_manager", "is_employee")
    search_fields = ("email",)
    list_filter = ("is_superadmin", "is_hr", "is_manager", "is_employee")

    fieldsets = (
        ("Login Info", {
            "fields": ("email",)
        }),
        ("Roles", {
            "fields": ("is_superadmin", "is_hr", "is_manager", "is_employee")
        }),
        ("Employee Mapping", {
            "fields": ("employee",)
        }),
    )

    def get_queryset(self, request):
        """Hide superadmins from normal user panel"""
        qs = super().get_queryset(request)
        return qs.exclude(is_superadmin=True)

    def save_model(self, request, obj, form, change):
        """AUTO create password + employee record"""
        if not obj.hashed_password:
            password = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
            obj.hashed_password = make_password(password)
            print(f"Generated Password for {obj.email}: {password}")

        if (obj.is_employee or obj.is_hr or obj.is_manager) and not obj.employee:
            emp = Employee.objects.create(
                empid="EMP" + str(random.randint(1000, 9999)),
                password=obj.hashed_password,
                name=obj.email.split("@")[0],
                email=obj.email
            )
            obj.employee = emp

        super().save_model(request, obj, form, change)

class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "empid")
    search_fields = ("name", "email", "empid")



# admin.site.register(User, UserAdmin)

admin.site.register(SuperAdminUser, SuperAdminAdmin)

# admin.site.register(Employee, EmployeeAdmin)
# admin.site.register(EmployeeManagerMap)
# admin.site.register(TimeLog)
# admin.site.register(Environment)
# admin.site.register(MissReport)
