from django.http import JsonResponse
from user.models import User, Employee
from user.utils.auth import decode_access_token
from .serializers import LeaveBalanceCreateSerializer, LeaveRequestCreateSerializer, LeaveRequestListSerializer, LeaveBalanceSerializer, LeaveRequestDetailSerializer,HolidayCreateSerializer,HolidayListSerializer
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
from .models import LeaveRequest, LeaveBalance,Holiday
from .utils import calculate_leave_with_weekend_sandwich
from user.models import EmployeeManagerMap
from datetime import datetime, date
from decimal import Decimal
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from user.permissions import JWTAuthenticationPermission,IsHRorSuperAdmin, IsHR, IsManager, IsEmployee ,IsHRManagerAdmin

AUTH_HEADER = openapi.Parameter(
    "Authorization",
    openapi.IN_HEADER,
    description="Bearer <JWT token>",
    type=openapi.TYPE_STRING,
    required=True,
)


@swagger_auto_schema(
    method="post",
    tags=["Leave Management"],
    operation_summary="Create Leave Balance",
    operation_description="HR or SuperAdmin can create leave balance for an employee",
    manual_parameters=[AUTH_HEADER],
    request_body=LeaveBalanceCreateSerializer,
    responses={
        201: "Leave balance created",
        400: "Validation error",
        403: "Permission denied",
    },
)

@api_view(["POST"])
@permission_classes([JWTAuthenticationPermission,IsHRorSuperAdmin])
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

@swagger_auto_schema(
    method="post",
    tags=["Leave Management"],
    operation_summary="Apply Leave",
    operation_description="Employee applies for leave",
    manual_parameters=[AUTH_HEADER],
    request_body=LeaveRequestCreateSerializer,
    responses={201: "Leave applied"},
)
@api_view(["POST"])
@permission_classes([JWTAuthenticationPermission,IsEmployee])
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

@swagger_auto_schema(
    method="get",
    tags=["Leave Management"],
    operation_summary="Get My Leaves",
    operation_description="Employee fetches own leave requests with balance",
    manual_parameters=[AUTH_HEADER],
)
@api_view(["GET"])
@permission_classes([JWTAuthenticationPermission,IsEmployee])
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

@swagger_auto_schema(
    method="get",
    tags=["Leave Management"],
    operation_summary="Get Leave By ID",
    manual_parameters=[AUTH_HEADER],
    responses={200: LeaveRequestDetailSerializer},
)
@api_view(["GET"])
@permission_classes([JWTAuthenticationPermission,IsHRManagerAdmin])
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


@swagger_auto_schema(
    method="get",
    tags=["Leave Management"],
    operation_summary="Get All Leaves",
    operation_description="HR/Admin/Manager can view leaves",
    manual_parameters=[AUTH_HEADER],
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

@swagger_auto_schema(
    method="patch",
    tags=["Leave Management"],
    operation_summary="Update Leave Request",
    manual_parameters=[AUTH_HEADER],
)
@api_view(["PATCH"])
@permission_classes([JWTAuthenticationPermission,IsEmployee])
def update_leave_request(request, leave_id):

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

    VALID_LEAVE_TYPES = {"sick", "optional", "casual", "earned"}

    try:
        leave = LeaveRequest.objects.select_related(
            "employee"
        ).get(id=leave_id, employee=employee)

        if leave.status in ["approved", "rejected"]:
            return Response(
                {"detail": f"Cannot update leave once it is {leave.status}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        leave_type = request.data.get("leave_type")
        start_date = request.data.get("start_date")
        end_date = request.data.get("end_date")
        reason = request.data.get("reason")
        half_day_start_type = request.data.get("half_day_start_type")
        half_day_end_type = request.data.get("half_day_end_type")
        attachment = request.FILES.get("attachment")

        if leave_type:
            if leave_type.lower() not in VALID_LEAVE_TYPES:
                return Response(
                    {"detail": f"Invalid leave type: {leave_type}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            leave.leave_type = leave_type.lower()

        if start_date:
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            leave.start_date = start_date

        if end_date:
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
            leave.end_date = end_date

        if reason is not None:
            leave.reason = reason

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

        leave.half_day_start_type = half_day_start_type
        leave.half_day_end_type = half_day_end_type

        if leave.start_date and leave.end_date:

            if leave.start_date > leave.end_date:
                return Response(
                    {"detail": "Start date cannot be after end date"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if leave.start_date == leave.end_date:
                if half_day_start_type or half_day_end_type:
                    leave.total_days = Decimal("0.5")
                else:
                    leave.total_days = Decimal("1.0")
            else:
                total_days = (leave.end_date - leave.start_date).days + 1
                if half_day_start_type:
                    total_days -= 0.5
                if half_day_end_type:
                    total_days -= 0.5

                leave.total_days = Decimal(total_days)

        if attachment:
            upload_dir = os.path.join(settings.MEDIA_ROOT, "uploads")
            os.makedirs(upload_dir, exist_ok=True)

            file_path = f"uploads/{attachment.name}"
            full_path = os.path.join(settings.MEDIA_ROOT, file_path)

            with open(full_path, "wb+") as destination:
                for chunk in attachment.chunks():
                    destination.write(chunk)

            leave.attachment = file_path

        leave.save()

        serializer = LeaveRequestDetailSerializer(leave)
        return Response(serializer.data, status=status.HTTP_200_OK)

    except LeaveRequest.DoesNotExist:
        return Response(
            {"detail": "Leave request not found"},
            status=status.HTTP_404_NOT_FOUND
        )

    except Exception as e:
        return Response(
            {"detail": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
from django.views.decorators.csrf import csrf_exempt


@swagger_auto_schema(
    method="patch",
    tags=["Leave Management"],
    operation_summary="Update Leave Balance",
    operation_description="HR or Admin updates employee leave balance",
    manual_parameters=[AUTH_HEADER],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "sick_leave": openapi.Schema(type=openapi.TYPE_NUMBER),
            "casual_leave": openapi.Schema(type=openapi.TYPE_NUMBER),
            "earned_leave": openapi.Schema(type=openapi.TYPE_NUMBER),
            "optional_leave": openapi.Schema(type=openapi.TYPE_NUMBER),
        },
    ),
)
@csrf_exempt
@api_view(["PATCH"])
@permission_classes([JWTAuthenticationPermission,IsHRorSuperAdmin])
def update_leave_balance(request, employee_id):

    user, error_response = authenticate_request(request)
    if error_response:
        return error_response

    if not (user.is_superadmin or user.is_hr):
        return Response(
            {"detail": "You don't have permission to update leave balance."},
            status=status.HTTP_403_FORBIDDEN
        )

    employee = Employee.objects.filter(empid=employee_id).first()
    if not employee:
        return Response(
            {"detail": "Employee not found"},
            status=status.HTTP_404_NOT_FOUND
        )

    balance, created = LeaveBalance.objects.get_or_create(
        employee=employee,
        defaults={"updated_by": user}
    )

    sick_leave = request.data.get("sick_leave")
    casual_leave = request.data.get("casual_leave")
    optional_leave = request.data.get("optional_leave")
    earned_leave = request.data.get("earned_leave")

    if sick_leave is not None:
        balance.sick_leave += float(Decimal(sick_leave))
        balance.total_sick_leave += float(Decimal(sick_leave))

    if casual_leave is not None:
        balance.casual_leave += float(Decimal(casual_leave))
        balance.total_casual_leave += float(Decimal(casual_leave))

    if optional_leave is not None:
        balance.optional_leave += float(Decimal(optional_leave))
        balance.total_optional_leave += float(Decimal(optional_leave))

    if earned_leave is not None:
        balance.earned_leave += float(Decimal(earned_leave))
        balance.total_earned_leave += float(Decimal(earned_leave))

    balance.updated_by = user
    balance.save()

    return Response(
        {
            "message": "Leave balance created"
            if created
            else "Leave balance updated successfully"
        },
        status=status.HTTP_200_OK
    )


@swagger_auto_schema(
    method="patch",
    tags=["Leave Management"],
    operation_summary="Approve or Reject Leave",
    manual_parameters=[AUTH_HEADER],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["status"],
        properties={
            "status": openapi.Schema(
                type=openapi.TYPE_STRING,
                enum=["approved", "rejected"],
            ),
            "comment": openapi.Schema(type=openapi.TYPE_STRING),
        },
    ),
)
@api_view(["PATCH"])
@permission_classes([JWTAuthenticationPermission,IsHRManagerAdmin])
def update_leave_status(request, leave_id):

    user, error_response = authenticate_request(request)
    if error_response:
        return error_response

    status_value = request.data.get("status")
    comment = request.data.get("comment")

    if status_value not in {"approved", "rejected"}:
        return Response(
            {"detail": "Status must be 'approved' or 'rejected'"},
            status=status.HTTP_400_BAD_REQUEST
        )

    if not (user.is_superadmin or user.is_hr or user.is_manager):
        return Response(
            {"detail": "You don't have permission to approve/reject the leave"},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        leave = LeaveRequest.objects.select_related("employee").get(id=leave_id)
    except LeaveRequest.DoesNotExist:
        return Response(
            {"detail": "Leave request not found"},
            status=status.HTTP_404_NOT_FOUND
        )

    employee = leave.employee

    if user.is_manager:
        is_managed = EmployeeManagerMap.objects.filter(
            manager=user,
            employee=employee
        ).exists()

        if not is_managed:
            return Response(
                {"detail": "You don't have permission to approve/reject current employee leave"},
                status=status.HTTP_403_FORBIDDEN
            )

    if status_value == leave.status:
        return Response(
            {"detail": f"Leave is already {leave.status}"},
            status=status.HTTP_400_BAD_REQUEST
        )

    # APPROVE 
    if status_value == "approved":

        balance = LeaveBalance.objects.filter(employee=employee).first()
        if not balance:
            return Response(
                {"detail": "Leave balance not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        leave_days = float(leave.total_days)
        remaining = leave_days

        deducted = {
            "sick": 0.0,
            "casual": 0.0,
            "earned": 0.0,
            "optional": 0.0,
        }

        def deduct(field, amount):
            current = float(getattr(balance, field))
            if current <= 0:
                return 0.0
            to_deduct = min(current, amount)
            setattr(balance, field, round(current - to_deduct, 1))
            return to_deduct

        if leave.leave_type == "optional":
            if balance.optional_leave < remaining:
                return Response(
                    {"detail": "Insufficient optional leave balance"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            deducted["optional"] = deduct("optional_leave", remaining)
            remaining -= deducted["optional"]

        else:
            primary = leave.leave_type
            deducted[primary] = deduct(f"{primary}_leave", remaining)
            remaining -= deducted[primary]

            if remaining > 0 and primary != "casual":
                deducted["casual"] = deduct("casual_leave", remaining)
                remaining -= deducted["casual"]

            if remaining > 0 and primary != "earned":
                deducted["earned"] = deduct("earned_leave", remaining)
                remaining -= deducted["earned"]

        leave.sick_deducted = Decimal(str(deducted["sick"]))
        leave.casual_deducted = Decimal(str(deducted["casual"]))
        leave.earned_deducted = Decimal(str(deducted["earned"]))
        leave.optional_deducted = Decimal(str(deducted["optional"]))

        leave.leave_without_pay = round(remaining, 1)
        leave.status = "approved"
        leave.approve_date = date.today()
        leave.approve_comment = comment
        leave.action_by = user

        balance.save()
        leave.save()

        return Response(
            {
                "message": "Leave approved",
                "leave_without_pay": leave.leave_without_pay,
                "deductions": deducted,
            },
            status=status.HTTP_200_OK
        )

    #REJECT
    if status_value == "rejected":

        if leave.status == "approved":
            balance = LeaveBalance.objects.filter(employee=employee).first()
            if not balance:
                return Response(
                    {"detail": "Leave balance not found"},
                    status=status.HTTP_404_NOT_FOUND
                )

            def restore(field, amount):
                current = float(getattr(balance, field))
                setattr(balance, field, round(current + float(amount), 1))

            restore("sick_leave", leave.sick_deducted)
            restore("casual_leave", leave.casual_deducted)
            restore("earned_leave", leave.earned_deducted)
            restore("optional_leave", leave.optional_deducted)

            balance.save()

            leave.sick_deducted = 0
            leave.casual_deducted = 0
            leave.earned_deducted = 0
            leave.optional_deducted = 0
            leave.leave_without_pay = 0

        leave.status = "rejected"
        leave.reject_date = date.today()
        leave.reject_comment = comment
        leave.action_by = user
        leave.save()

        return Response(
            {"message": "Leave rejected"},
            status=status.HTTP_200_OK
        )


@swagger_auto_schema(
    method="get",
    tags=["Leave Management"],
    operation_summary="Get Leave Balance by Employee ID",
    manual_parameters=[AUTH_HEADER],
)
@api_view(["GET"])
@permission_classes([JWTAuthenticationPermission,IsHRorSuperAdmin])
def get_leave_balance(request, empid):
    token = request.headers.get("Authorization")
    if not token or not token.startswith("Bearer "):
        return JsonResponse({"error": "Authorization header missing"}, status=401)

    token = token.split(" ")[1]
    payload = decode_access_token(token)
    if not payload:
        return JsonResponse({"error": "Invalid token"}, status=401)

    current_user_email = payload.get("sub")
    current_user = User.objects.filter(email=current_user_email).first()
    if not current_user:
        return JsonResponse({"error": "User not found"}, status=404)

    employee = Employee.objects.filter(empid=empid).first()
    if not employee:
        return JsonResponse({"error": "Employee not found"}, status=404)

    if current_user.employee:
        if employee.id != current_user.employee.id:
            if not (current_user.is_superadmin or current_user.is_hr):
                return JsonResponse(
                    {"error": "You can only view your own leave balance"},
                    status=403
                )

    balance = LeaveBalance.objects.filter(employee=employee).first()
    if not balance:
        return JsonResponse(
            {"error": "Leave balance not found"},
            status=404
        )

    data = {
        "employee_id": employee.id,
        "employee_code": employee.empid,
        "employee_name": employee.name,
        "sick_leave": balance.sick_leave,
        "casual_leave": balance.casual_leave,
        "earned_leave": balance.earned_leave,
        "optional_leave": balance.optional_leave,
        "total_sick_leave": balance.total_sick_leave,
        "total_casual_leave": balance.total_casual_leave,
        "total_earned_leave": balance.total_earned_leave,
        "total_optional_leave": balance.total_optional_leave,
    }

    return JsonResponse(data, status=200)



@swagger_auto_schema(
    method="delete",
    tags=["Leave Management"],
    operation_summary="Delete Leave Request",
    operation_description="Employee deletes pending leave",
    manual_parameters=[AUTH_HEADER],
)
@api_view(["DELETE"])
@permission_classes([JWTAuthenticationPermission,IsHRorSuperAdmin])
def delete_leave_request(request, leave_id):
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

    employee = getattr(current_user, "employee", None)
    if not employee:
        return JsonResponse({"error": "Employee not found"}, status=404)

    leave = LeaveRequest.objects.filter(id=leave_id).first()
    if not leave:
        return JsonResponse({"error": "Leave request not found"}, status=404)

    if leave.employee_id != employee.id:
        return JsonResponse(
            {"error": "Not authorized to delete this leave"},
            status=403
        )

    if leave.status in ["approved", "rejected"]:
        return JsonResponse(
            {"error": f"Cannot delete a {leave.status} leave request"},
            status=400
        )

    leave.delete()

    return JsonResponse(
        {
            "message": "Leave request deleted successfully",
            "employee": {
                "id": employee.id,
                "empid": employee.empid,
                "name": employee.name,
            },
            "status": "Success"
        },
        status=200
    )


@api_view(["POST"])
@permission_classes([JWTAuthenticationPermission, IsHRorSuperAdmin])
def create_holiday(request):

    # 🔹 Token check (same as your API)
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

    # 🔹 Role check
    if not (current_user.is_superadmin or current_user.is_hr):
        return JsonResponse(
            {"error": "Only SuperAdmin or HR can create holiday"},
            status=403
        )

    # 🔹 Validate request data
    serializer = HolidayCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return JsonResponse(serializer.errors, status=400)

    festival_date = serializer.validated_data["festival_date"]

    # 🔹 Duplicate check
    if Holiday.objects.filter(festival_date=festival_date).exists():
        return JsonResponse(
            {"error": "Holiday already exists for this date"},
            status=400
        )

    # 🔹 Create holiday
    Holiday.objects.create(
        festival_date=serializer.validated_data["festival_date"],
        festival_name=serializer.validated_data["festival_name"],
        created_by=current_user,
        updated_by=current_user
    )

    return JsonResponse(
        {"message": "Holiday created successfully"},
        status=201
    )

@api_view(["GET"])
@permission_classes([JWTAuthenticationPermission])
def get_holidays(request):
    """
    Accessible by: Admin, HR, Manager, Employee
    """

    holidays = Holiday.objects.all().order_by("festival_date")
    serializer = HolidayListSerializer(holidays, many=True)

    return JsonResponse(
        {
            "count": len(serializer.data),
            "holidays": serializer.data
        },
        status=200
    )


@api_view(["PATCH"])
@permission_classes([JWTAuthenticationPermission, IsHRorSuperAdmin])
def update_holiday(request, festival_id):

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
            {"error": "Only SuperAdmin or HR can update holiday"},
            status=403
        )

    holiday = Holiday.objects.filter(id=festival_id).first()
    if not holiday:
        return JsonResponse(
            {"error": "Holiday not found"},
            status=404
        )

    serializer = HolidayCreateSerializer(
        holiday,
        data=request.data,
        partial=True
    )

    if not serializer.is_valid():
        return JsonResponse(serializer.errors, status=400)

    new_date = serializer.validated_data.get("festival_date")
    if new_date:
        if Holiday.objects.filter(festival_date=new_date).exclude(id=festival_id).exists():
            return JsonResponse(
                {"error": "Another holiday already exists for this date"},
                status=400
            )

    serializer.save(updated_by=current_user)

    return JsonResponse(
        {"message": "Holiday updated successfully"},
        status=200
    )
