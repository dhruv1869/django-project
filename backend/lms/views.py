from django.http import JsonResponse
from user.models import User, Employee
from user.utils.auth import decode_access_token
from .models import LeaveBalance
from .serializers import LeaveBalanceCreateSerializer, LeaveRequestCreateSerializer, LeaveRequestListSerializer, LeaveBalanceSerializer, LeaveRequestDetailSerializer
import os
from datetime import date
from decimal import Decimal
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from user.utils.auth import authenticate_request
from user.models import Employee
from .models import LeaveRequest, LeaveBalance
from .utils import calculate_leave_with_weekend_sandwich
from user.models import EmployeeManagerMap

@api_view(["POST"])
@permission_classes([AllowAny])
def create_leave_balance(request):
    token = request.headers.get("Authorization")
    if not token or not token.startswith("Bearer "):
        return JsonResponse(
            {"error": "Authorization header missing"},
            status=401
        )

    token = token.split(" ")[1]
    payload = decode_access_token(token)
    if not payload:
        return JsonResponse({"error": "Invalid token"}, status=401)

    current_user_email = payload.get("sub")
    current_user = User.objects.filter(email=current_user_email).first()
    if not current_user:
        return JsonResponse({"error": "User not found"}, status=404)

    if not (current_user.is_superadmin or current_user.is_hr):
        return JsonResponse(
            {"error": "Only SuperAdmin or HR can create leave balance"},
            status=403
        )

    serializer = LeaveBalanceCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return JsonResponse(serializer.errors, status=400)

    employee_id = serializer.validated_data["employee_id"]
    employee = Employee.objects.filter(id=employee_id).first()
    if not employee:
        return JsonResponse({"error": "Employee not found"}, status=404)

    if LeaveBalance.objects.filter(employee=employee).exists():
        return JsonResponse(
            {"error": "Leave balance already exists for this employee"},
            status=400
        )

    LeaveBalance.objects.create(
        employee=employee,
        sick_leave=serializer.validated_data.get("sick_leave", 0),
        casual_leave=serializer.validated_data.get("casual_leave", 0),
        optional_leave=serializer.validated_data.get("optional_leave", 0),
        earned_leave=serializer.validated_data.get("earned_leave", 0),
        total_sick_leave=serializer.validated_data.get("total_sick_leave", 0),
        total_casual_leave=serializer.validated_data.get("total_casual_leave", 0),
        total_optional_leave=serializer.validated_data.get("total_optional_leave", 0),
        total_earned_leave=serializer.validated_data.get("total_earned_leave", 0),
        updated_by=current_user
    )

    return JsonResponse(
        {"message": "Leave balance created successfully"},
        status=201
    )

@api_view(["POST"])
@permission_classes([AllowAny])
def apply_leave(request):

    user, error_response = authenticate_request(request)
    if error_response:
        return error_response

    try:
        employee = user.employee
    except Employee.DoesNotExist:
        return Response(
            {"detail": "User is not linked to an employee."},
            status=status.HTTP_403_FORBIDDEN
        )

    employee_leave_balance = LeaveBalance.objects.filter(employee=employee).first()
    if not employee_leave_balance:
        return Response(
            {"detail": "Leave Balance not set. Contact HR."},
            status=status.HTTP_403_FORBIDDEN
        )

    serializer = LeaveRequestCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    leave_type = serializer.validated_data["leave_type"]
    start_date = serializer.validated_data["start_date"]
    end_date = serializer.validated_data["end_date"]
    reason = serializer.validated_data.get("reason")
    half_day_start_type = serializer.validated_data.get("half_day_start_type")
    half_day_end_type = serializer.validated_data.get("half_day_end_type")
    attachment = serializer.validated_data.get("attachment")

    VALID_LEAVE_TYPES = {"sick", "optional", "casual", "earned"}
    if leave_type not in VALID_LEAVE_TYPES:
        return Response(
            {"detail": f"Invalid leave type : {leave_type}"},
            status=status.HTTP_400_BAD_REQUEST
        )

    if start_date > end_date:
        return Response(
            {"detail": "Start date cannot be after end date"},
            status=status.HTTP_400_BAD_REQUEST
        )

    current_date = date.today()
    if current_date > start_date or current_date > end_date:
        return Response(
            {"detail": "Leave date has already passed."},
            status=status.HTTP_400_BAD_REQUEST
        )

    if half_day_start_type and half_day_start_type.lower() not in {"first", "second"}:
        return Response(
            {"detail": "half_day_start_type must be either 'first' or 'second'"},
            status=status.HTTP_400_BAD_REQUEST
        )

    if half_day_end_type and half_day_end_type.lower() not in {"first", "second"}:
        return Response(
            {"detail": "half_day_end_type must be either 'first' or 'second'"},
            status=status.HTTP_400_BAD_REQUEST
        )

    is_already_applied = LeaveRequest.objects.filter(
        employee=employee,
        status__in=["pending", "approved"],
        start_date__lte=end_date,
        end_date__gte=start_date
    ).exists()

    if is_already_applied:
        return Response(
            {"detail": "Duplicate leave: Dates already applied."},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        if start_date == end_date:
            if half_day_start_type or half_day_end_type:
                sandwich_days = 0
                total_days = Decimal("0.5")
            else:
                sandwich_days = 0
                total_days = Decimal("1.0")
        else:
            total_days, sandwich_days = calculate_leave_with_weekend_sandwich(
                start_date,
                end_date,
                half_day_start_type,
                half_day_end_type
            )
            total_days = Decimal(total_days)

            if half_day_start_type:
                total_days -= Decimal("0.5")
            if half_day_end_type:
                total_days -= Decimal("0.5")

    except Exception as e:
        return Response(
            {"detail": str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )

    file_path = None
    if attachment:
        upload_dir = os.path.join(settings.MEDIA_ROOT, "uploads")
        os.makedirs(upload_dir, exist_ok=True)

        file_path = f"uploads/{attachment.name}"
        full_path = os.path.join(settings.MEDIA_ROOT, file_path)

        with open(full_path, "wb+") as destination:
            for chunk in attachment.chunks():
                destination.write(chunk)

    LeaveRequest.objects.create(
        employee=employee,
        leave_type=leave_type,
        start_date=start_date,
        end_date=end_date,
        total_days=total_days,
        reason=reason,
        half_day_start_type=half_day_start_type,
        half_day_end_type=half_day_end_type,
        attachment=file_path
    )

    return Response(
        {
            "message": f"Leave request for {total_days} days submitted successfully, including {sandwich_days} sandwich weekend day(s).",
            "status": "Success"
        },
        status=status.HTTP_201_CREATED
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def get_my_leaves(request):

    user, error_response = authenticate_request(request)
    if error_response:
        return error_response

    try:
        employee = user.employee
    except Employee.DoesNotExist:
        return Response(
            {"detail": "Employee not found"},
            status=status.HTTP_404_NOT_FOUND
        )

    leaves = LeaveRequest.objects.filter(
        employee=employee
    ).order_by("-start_date")

    balance = LeaveBalance.objects.filter(employee=employee).first()

    leaves_data = LeaveRequestListSerializer(leaves, many=True).data
    balance_data = (
        LeaveBalanceSerializer(balance).data if balance else None
    )

    return Response(
        {
            "leaves": leaves_data,
            "balance": balance_data
        },
        status=status.HTTP_200_OK
    )

@api_view(["GET"])
@permission_classes([AllowAny])
def get_leave_by_id(request, leave_id):

    user, error_response = authenticate_request(request)
    if error_response:
        return error_response

    try:
        leave = LeaveRequest.objects.select_related(
            "employee"
        ).get(id=leave_id)
    except LeaveRequest.DoesNotExist:
        return Response(
            {"detail": "Leave request not found"},
            status=status.HTTP_404_NOT_FOUND
        )

    serializer = LeaveRequestDetailSerializer(leave)

    return Response(
        serializer.data,
        status=status.HTTP_200_OK
    )

@api_view(["GET"])
@permission_classes([AllowAny])
def get_all_leaves(request):

    user, error_response = authenticate_request(request)
    if error_response:
        return error_response

    if not (user.is_hr or user.is_superadmin or user.is_manager):
        return Response(
            {"detail": "Not authorised to get leaves"},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        if user.is_manager:
            employee_ids = EmployeeManagerMap.objects.filter(
                manager_id=user.id
            ).values_list("employee_id", flat=True)

            leaves = LeaveRequest.objects.filter(
                employee_id__in=employee_ids
            ).select_related("employee")

        else:
            leaves = LeaveRequest.objects.all().select_related("employee")

        serializer = LeaveRequestDetailSerializer(leaves, many=True)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )

    except Exception as e:
        return Response(
            {"detail": f"An error occurred: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
