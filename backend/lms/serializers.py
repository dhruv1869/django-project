from rest_framework import serializers
from .models import LeaveBalance

class LeaveBalanceCreateSerializer(serializers.ModelSerializer):
    employee_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = LeaveBalance
        fields = [
            "employee_id",
            "sick_leave",
            "casual_leave",
            "optional_leave",
            "earned_leave",
            "total_sick_leave",
            "total_casual_leave",
            "total_optional_leave",
            "total_earned_leave",
        ]

from rest_framework import serializers
from .models import LeaveRequest


class LeaveRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveRequest
        fields = [
            "leave_type",
            "start_date",
            "end_date",
            "reason",
            "half_day_start_type",
            "half_day_end_type",
            "attachment",
        ]

class LeaveRequestListSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveRequest
        fields = "__all__"


class LeaveBalanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveBalance
        fields = "__all__"

class LeaveRequestDetailSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(
        source="employee.empid",
        read_only=True
    )

    class Meta:
        model = LeaveRequest
        fields = "__all__"