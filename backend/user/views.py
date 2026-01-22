import json, random, string, os
from uuid import uuid4
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .utils.auth import verify_password, create_token, hash_password ,decode_access_token
from .models import User, Employee, EmployeeManagerMap
from django.contrib.auth.hashers import check_password, make_password
import shutil
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.http import Http404
from .serializers import (
    LoginSerializer,
    CreateEmployeeSerializer,
    EmployeeSerializer,
    UpdateEmployeeSerializer,
    ChangePasswordSerializer,
    DeleteEmployeeSerializer,
    AddPhotoSerializer,
    GetEmployeePhotosSerializer,
    DeletePhotoSerializer,
    GetManagersSerializer,
    GetManagerEmployeesSerializer
)
from .models import User, Employee
from .utils.auth import create_token, decode_access_token, verify_password
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.decorators import api_view, permission_classes
from .permissions import JWTAuthenticationPermission,IsHRorSuperAdmin, IsHR, IsManager, IsEmployee
from django.http.multipartparser import MultiPartParser

ALLOWED_IMAGE_TYPES = ["image/png", "image/jpeg", "image/jpg"]
UPLOAD_FOLDER = os.path.join(settings.MEDIA_ROOT, "image")

PHOTOS_BASE_PATH = os.path.join(settings.MEDIA_ROOT, "media/employee")
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

login_request_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    required=["email", "password"],
    properties={
        "email": openapi.Schema(
            type=openapi.TYPE_STRING,
            example="admin@example.com"
        ),
        "password": openapi.Schema(
            type=openapi.TYPE_STRING,
            example="admin123"
        ),
    },
)

login_response_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "username": openapi.Schema(
            type=openapi.TYPE_STRING,
            example="admin@example.com"
        ),
        "access_token": openapi.Schema(
            type=openapi.TYPE_STRING,
            example="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
        ),
        "token_type": openapi.Schema(
            type=openapi.TYPE_STRING,
            example="bearer"
        ),
    },
)
@swagger_auto_schema(
    method="post",
    request_body=login_request_schema,
    responses={200: login_response_schema},
    tags=["Authentication"],
)
@api_view(["POST"])                
@permission_classes([AllowAny])   
def login_user(request):

    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=400)

    try:
        data = json.loads(request.body)

        serializer = LoginSerializer(data=data)
        if not serializer.is_valid():
            return JsonResponse(serializer.errors, status=400)

        email = serializer.validated_data["email"]
        password = serializer.validated_data["password"]

        user = User.objects.filter(email=email).first()
        if not user or not verify_password(password, user.hashed_password):
            return JsonResponse(
                {"error": "Invalid email/password"},
                status=401
            )

        token = create_token({"sub": user.email})

        return JsonResponse(
            {
                "username": user.email,
                "access_token": token,
                "token_type": "bearer",
            },
            status=200,
        )

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
    
@swagger_auto_schema(
    method="post", 
    operation_summary="Create Employee",
    operation_description="Create employee with image upload",
    manual_parameters=[
        openapi.Parameter(
            "Authorization",
            openapi.IN_HEADER,
            description="Bearer <token>",
            type=openapi.TYPE_STRING,
            required=True,
        )
    ],
    consumes=["multipart/form-data"],
    request_body=CreateEmployeeSerializer,
    responses={201: "Employee Created"},
    tags=["Employee"],
)
@api_view(["POST"])
@permission_classes([JWTAuthenticationPermission,IsHRorSuperAdmin|IsManager])
@csrf_exempt
def create_user(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=400)

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

    if not (current_user.is_superadmin or current_user.is_hr or current_user.is_manager):
        return JsonResponse(
            {"error": "Only SuperAdmin, HR, or Manager can create users"},
            status=403
        )

    if current_user.is_manager:
        if request.POST.get("is_superadmin") == "true":
            return JsonResponse(
                {"error": "Manager cannot create SuperAdmin"},
                status=403
            )

    try:
        file = request.FILES.get("file")
        if not file:
            return JsonResponse({"error": "Image file required"}, status=400)

        if file.content_type not in ALLOWED_IMAGE_TYPES:
            return JsonResponse({"error": "Invalid image type"}, status=400)

        # Prepare serializer data
        serializer_data = {
            "username": request.POST.get("username"),
            "email": request.POST.get("email"),
            "empid": request.POST.get("empid"),
            "is_superadmin": request.POST.get("is_superadmin") == "true",
            "is_hr": request.POST.get("is_hr") == "true",
            "is_manager": request.POST.get("is_manager") == "true",
            "manager_email": request.POST.get("manager_email")
        }

        serializer = CreateEmployeeSerializer(data=serializer_data)
        if not serializer.is_valid():
            return JsonResponse(serializer.errors, status=400)

        result = serializer.save()
        employee = result["employee"]
        user = result["user"]
        password = result["password"]

        user.image.save(file.name, file, save=True)

        return JsonResponse({
            "message": "Employee created successfully",
            "username": employee.name,
            "email": employee.email,
            "empid": employee.empid,
            "password": password,
            "user_id": user.id,
            "image_url": user.image.url 
        }, status=201)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def to_bool(v):
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    return str(v).strip().lower() in ["true", "1", "yes"]

@swagger_auto_schema(
    method="get", 
    operation_summary="Get Employees",
    manual_parameters=[
        openapi.Parameter(
            "Authorization",
            openapi.IN_HEADER,
            description="Bearer <token>",
            type=openapi.TYPE_STRING,
            required=True,
        )
    ],
    responses={200: EmployeeSerializer(many=True)},
    tags=["Employee"],
)
@api_view(["GET"])
@permission_classes([JWTAuthenticationPermission, IsHRorSuperAdmin])
def get_employees(request):

    current_user = request.user_obj   

    try:
        if current_user.is_manager:
            mapping = EmployeeManagerMap.objects.filter(manager=current_user)
            employees = Employee.objects.filter(
                id__in=[m.employee.id for m in mapping]
            )
        else:
            employees = Employee.objects.all()

        if not employees.exists():
            return JsonResponse({"error": "No employees found"}, status=404)

        serializer = EmployeeSerializer(employees, many=True)
        data = serializer.data

        for emp_dict in data:
            emp_id = emp_dict["id"]
            user = User.objects.filter(employee_id=emp_id).first()
            if user and user.image:
                emp_dict["image_url"] = request.build_absolute_uri(user.image.url)
            else:
                emp_dict["image_url"] = None

        return JsonResponse({"employees": data}, safe=False)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@swagger_auto_schema(
    method="get", 
    operation_summary="Get Employee By ID",
    manual_parameters=[
        openapi.Parameter(
            "Authorization",
            openapi.IN_HEADER,
            type=openapi.TYPE_STRING,
            required=True,
        )
    ],
    responses={200: EmployeeSerializer},
    tags=["Employee"],
)

@api_view(["GET"])
@permission_classes([JWTAuthenticationPermission, IsHRorSuperAdmin])
@csrf_exempt
def get_employee_by_id(request, id):
    if request.method != "GET":
        return JsonResponse({"error": "GET request required"}, status=400)

    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        return JsonResponse({"error": "Authorization missing"}, status=401)

    token = auth.split(" ")[1]
    payload = decode_access_token(token)
    if not payload:
        return JsonResponse({"error": "Invalid token"}, status=401)

    email = payload.get("sub")
    current_user = User.objects.filter(email=email).first()
    if not current_user:
        return JsonResponse({"error": "User not found"}, status=404)

    if not (current_user.is_superadmin or current_user.is_hr or current_user.is_manager):
        return JsonResponse({"error": "Permission denied"}, status=403)

    emp_obj = Employee.objects.filter(empid=id).first()
    if not emp_obj:
        return JsonResponse({"error": "Employee not found"}, status=404)

    if current_user.is_manager:
        if not EmployeeManagerMap.objects.filter(
            manager=current_user, employee=emp_obj
        ).exists():
            return JsonResponse({"error": "Access denied"}, status=403)

    serializer = EmployeeSerializer(emp_obj)
    employee = serializer.data

    user_obj = User.objects.filter(employee=emp_obj).first()

    if user_obj and user_obj.image:
        employee["image_url"] = request.build_absolute_uri(user_obj.image.url)
    else:
        employee["image_url"] = None

    return JsonResponse({"employee": employee})

    
@swagger_auto_schema(
    method="patch", 
    operation_summary="Update Employee",
    manual_parameters=[
        openapi.Parameter(
            "Authorization",
            openapi.IN_HEADER,
            type=openapi.TYPE_STRING,
            required=True,
        )
    ],
    consumes=["multipart/form-data"],
    request_body=UpdateEmployeeSerializer,
    responses={200: "Updated"},
    tags=["Employee"],
)
@api_view(["PATCH"])
@permission_classes([JWTAuthenticationPermission,IsHRorSuperAdmin])
@csrf_exempt
def update_employee(request):
    from django.http.multipartparser import MultiPartParser

    parser = MultiPartParser(request.META, request, request.upload_handlers)
    data, files = parser.parse()

    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        return JsonResponse({"error": "Authorization header missing"}, status=401)

    token = auth.split(" ")[1]
    payload = decode_access_token(token)
    if not payload:
        return JsonResponse({"error": "Invalid token"}, status=401)

    current_user = User.objects.filter(email=payload.get("sub")).first()
    if not current_user:
        return JsonResponse({"error": "User not found"}, status=404)

    if not (current_user.is_superadmin or current_user.is_hr):
        return JsonResponse(
            {"error": "Only superadmin or HR can update employees"},
            status=403
        )

    serializer = UpdateEmployeeSerializer(data=data)
    if not serializer.is_valid():
        return JsonResponse(serializer.errors, status=400)

    validated = serializer.validated_data
    empid = validated["empid"]

    employee_obj = Employee.objects.filter(empid=empid).first()
    if not employee_obj:
        return JsonResponse({"error": "Employee not found"}, status=404)

    user = User.objects.filter(employee=employee_obj).first()
    if not user:
        return JsonResponse({"error": "User not found for employee"}, status=404)

    try:
        if validated.get("name"):
            employee_obj.name = validated["name"]

        if validated.get("email"):
            employee_obj.email = validated["email"]

        employee_obj.save()

        if validated.get("email"):
            user.email = validated["email"]

        if validated.get("is_superadmin") is not None:
            user.is_superadmin = validated["is_superadmin"]

        if validated.get("is_hr") is not None:
            user.is_hr = validated["is_hr"]

        if validated.get("is_manager") is not None:
            user.is_manager = validated["is_manager"]

        image_file = files.get("file")
        if image_file:
            user.image = image_file   
            user.save()

        return JsonResponse({
            "message": "Employee updated successfully",
            "empid": empid,
            "image_url": (
                request.build_absolute_uri(user.image.url)
                if user.image else None
            )
        })

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

    
@swagger_auto_schema(
    method="post",     
    operation_summary="Change Password",
    operation_description="Change user password using old password",
    request_body=ChangePasswordSerializer,
    responses={
        200: "Password changed successfully",
        400: "Validation error",
        401: "Incorrect old password",
        404: "User not found",
    },
    tags=["chnage pssword"],
)
@api_view(["POST"])
@permission_classes([JWTAuthenticationPermission,IsHRorSuperAdmin])
@csrf_exempt
def change_password(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    try:
        data = request.POST

        serializer = ChangePasswordSerializer(data=data)
        if not serializer.is_valid():
            return JsonResponse(serializer.errors, status=400)

        email = serializer.validated_data["email"]
        old_password = serializer.validated_data["old_password"]
        new_password = serializer.validated_data["new_password"]

        user = User.objects.filter(email=email).first()
        if not user:
            return JsonResponse({"error": "User not found"}, status=404)

        if not check_password(old_password, user.hashed_password):
            return JsonResponse({"error": "Incorrect old password"}, status=401)

        hashed_password = make_password(new_password)

        if user.is_employee:
            emp = Employee.objects.filter(email=email).first()
            if emp:
                emp.password = hashed_password
                emp.save()

        user.hashed_password = hashed_password
        user.save()

        return JsonResponse(
            {"message": "Password changed successfully"},
            status=200
        )

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@swagger_auto_schema(
    method="delete", 
    operation_summary="Delete Employee",
    manual_parameters=[
        openapi.Parameter(
            "Authorization",
            openapi.IN_HEADER,
            type=openapi.TYPE_STRING,
            required=True,
        )
    ],
    responses={200: "Deleted"},
    tags=["Employee"],
)
@api_view(["DELETE"])
@permission_classes([JWTAuthenticationPermission,IsHRorSuperAdmin])
@csrf_exempt
def delete_employee(request, empid):
    if request.method != "DELETE":
        return JsonResponse({"error": "DELETE request required"}, status=400)

    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        return JsonResponse({"error": "Authorization missing"}, status=401)

    token = auth.split(" ")[1]
    payload = decode_access_token(token)
    if not payload:
        return JsonResponse({"error": "Invalid token"}, status=401)

    email = payload.get("sub")
    current_user = User.objects.filter(email=email).first()
    if not current_user:
        return JsonResponse({"error": "User not found"}, status=404)

    if not (current_user.is_superadmin or current_user.is_hr):
        return JsonResponse(
            {"error": "Only Superadmin or HR can delete an employee"},
            status=403
        )

    try:
        serializer = DeleteEmployeeSerializer(data={"empid": empid})
        if not serializer.is_valid():
            return JsonResponse(serializer.errors, status=400)

        empid = serializer.validated_data["empid"]

        employee = Employee.objects.filter(empid=empid).first()
        if not employee:
            return JsonResponse({"error": "Employee not found"}, status=404)

        user = User.objects.filter(employee=employee).first()

        if user:
            if user.is_superadmin:
                return JsonResponse(
                    {"error": "Cannot delete a Superadmin"},
                    status=403
                )

            if user.is_hr and not current_user.is_superadmin:
                return JsonResponse(
                    {"error": "Only Superadmin can delete an HR"},
                    status=403
                )

            if user.id == current_user.id:
                return JsonResponse(
                    {"error": "You cannot delete yourself"},
                    status=403
                )

            user.delete()

        employee.delete()

        emp_dir = os.path.join(UPLOAD_FOLDER, str(empid))
        if os.path.exists(emp_dir):
            shutil.rmtree(emp_dir)

        return JsonResponse(
            {"message": "Employee and associated user deleted successfully"},
            status=200
        )

    except Exception as e:
        return JsonResponse(
            {"error": f"Internal server error: {str(e)}"},
            status=500
        )

@swagger_auto_schema(
    method="post",
    operation_summary="Add Employee Photo",
    consumes=["multipart/form-data"],
    manual_parameters=[
        openapi.Parameter(
            "Authorization",
            openapi.IN_HEADER,
            type=openapi.TYPE_STRING,
            required=True,
        )
    ],
    request_body=AddPhotoSerializer,
    tags=["Photos"],
)

@api_view(["POST"])
@permission_classes([JWTAuthenticationPermission, IsHR | IsManager])
@csrf_exempt
def add_photo(request, id):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=400)

    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        return JsonResponse({"error": "Authorization missing"}, status=401)

    token = auth.split(" ")[1]
    payload = decode_access_token(token)
    if not payload:
        return JsonResponse({"error": "Invalid token"}, status=401)

    current_user = User.objects.filter(email=payload.get("sub")).first()
    if not current_user:
        return JsonResponse({"error": "User not found"}, status=404)

    if not (current_user.is_superadmin or current_user.is_hr or current_user.is_manager):
        return JsonResponse(
            {"error": "You don't have permission to add photo"},
            status=403
        )

    parser = MultiPartParser(request.META, request, request.upload_handlers)
    data, files = parser.parse()

    serializer = AddPhotoSerializer(
        data={"empid": id, "file": files.get("file")}
    )
    if not serializer.is_valid():
        return JsonResponse(serializer.errors, status=400)

    employee = Employee.objects.filter(empid=id).first()
    if not employee:
        return JsonResponse({"error": "Employee not found"}, status=404)

    user = User.objects.filter(employee=employee).first()
    if not user:
        return JsonResponse({"error": "User not linked with employee"}, status=404)

    if current_user.is_manager:
        if not EmployeeManagerMap.objects.filter(
            manager=current_user,
            employee=employee
        ).exists():
            return JsonResponse(
                {"error": "You don't have access to this employee"},
                status=403
            )

    image_file = serializer.validated_data["file"]

    if user.image:
        user.image.delete(save=False)

    user.image = image_file
    user.save()

    image_url = request.build_absolute_uri(user.image.url)

    return JsonResponse(
        {
            "message": "Photo uploaded successfully",
            "image_url": image_url
        },
        status=201
    )

@swagger_auto_schema(
    method="get",
    operation_summary="Get Employee Photos",
    manual_parameters=[
        openapi.Parameter(
            "Authorization",
            openapi.IN_HEADER,
            type=openapi.TYPE_STRING,
            required=True,
        )
    ],
    tags=["Photos"],
)

@api_view(["GET"])
@permission_classes([JWTAuthenticationPermission, IsHR | IsManager])
@csrf_exempt
def get_employee_photos(request, empid):
    if request.method != "GET":
        return JsonResponse({"error": "GET request required"}, status=400)

    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        return JsonResponse({"error": "Authorization missing"}, status=401)

    token = auth.split(" ")[1]
    payload = decode_access_token(token)
    if not payload:
        return JsonResponse({"error": "Invalid token"}, status=401)

    current_user = User.objects.filter(email=payload.get("sub")).first()
    if not current_user:
        return JsonResponse({"error": "User not found"}, status=404)

    if not (current_user.is_superadmin or current_user.is_hr or current_user.is_manager):
        return JsonResponse(
            {"error": "You don't have permission to get photo"},
            status=403
        )

    serializer = GetEmployeePhotosSerializer(data={"empid": empid})
    if not serializer.is_valid():
        return JsonResponse(serializer.errors, status=400)

    employee = Employee.objects.filter(empid=empid).first()
    if not employee:
        return JsonResponse({"error": "Employee not found"}, status=404)

    if current_user.is_manager:
        if not EmployeeManagerMap.objects.filter(
            manager=current_user,
            employee=employee
        ).exists():
            return JsonResponse(
                {"error": "You don't have access to this employee"},
                status=403
            )

    user = User.objects.filter(employee=employee).first()
    if not user:
        return JsonResponse({"error": "User not linked with employee"}, status=404)

    if not user.image:
        return JsonResponse(
            {"image": None, "message": "No image uploaded"},
            status=200
        )

    image_url = request.build_absolute_uri(user.image.url)

    return JsonResponse(
        {"image": image_url},
        status=200
    )

@swagger_auto_schema(
    method="delete",
    operation_summary="Delete Employee Photo",
    manual_parameters=[
        openapi.Parameter(
            "Authorization",
            openapi.IN_HEADER,
            type=openapi.TYPE_STRING,
            required=True,
        )
    ],
    tags=["Photos"],
)
@api_view(["DELETE"])
@permission_classes([JWTAuthenticationPermission,IsHRorSuperAdmin])
@csrf_exempt
def delete_photo(request, id):
    if request.method != "DELETE":
        return JsonResponse({"error": "DELETE request required"}, status=405)

    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        return JsonResponse({"error": "Authorization missing"}, status=401)

    token = auth.split(" ")[1]
    payload = decode_access_token(token)
    if not payload:
        return JsonResponse({"error": "Invalid token"}, status=401)

    current_user = User.objects.filter(email=payload.get("sub")).first()
    if not current_user:
        return JsonResponse({"error": "User not found"}, status=404)

    if not (current_user.is_superadmin or current_user.is_hr or current_user.is_manager):
        return JsonResponse(
            {"error": "You don't have permission to delete photo"},
            status=403
        )

    serializer = DeletePhotoSerializer(data={"empid": id})
    if not serializer.is_valid():
        return JsonResponse(serializer.errors, status=400)

    empid = serializer.validated_data["empid"]

    employee = Employee.objects.filter(empid=empid).first()
    if not employee:
        return JsonResponse({"error": "Employee not found"}, status=404)

    if current_user.is_manager:
        if not EmployeeManagerMap.objects.filter(
            manager=current_user,
            employee=employee
        ).exists():
            return JsonResponse(
                {"error": "You don't have access to this employee"},
                status=403
            )

    user = User.objects.filter(employee=employee).first()
    if not user:
        return JsonResponse({"error": "User not linked with employee"}, status=404)

    if not user.image:
        return JsonResponse(
            {"error": "No image found to delete"},
            status=404
        )

    user.image.delete(save=False)   
    user.image = None
    user.save()

    return JsonResponse(
        {"message": "Employee image deleted successfully"},
        status=200
    )

@swagger_auto_schema(
    method="get",
    operation_summary="Get Managers",
    manual_parameters=[
        openapi.Parameter(
            "Authorization",
            openapi.IN_HEADER,
            type=openapi.TYPE_STRING,
            required=True,
        )
    ],
    tags=["Manager"],
)
@api_view(["GET"])
@permission_classes([JWTAuthenticationPermission, IsHRorSuperAdmin])
@csrf_exempt
def get_managers(request):
    if request.method != "GET":
        return JsonResponse({"error": "GET request required"}, status=400)

    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        return JsonResponse({"error": "Authorization missing"}, status=401)

    token = auth.split(" ")[1]
    payload = decode_access_token(token)
    if not payload:
        return JsonResponse({"error": "Invalid token"}, status=401)

    current_user = User.objects.filter(email=payload.get("sub")).first()
    if not current_user:
        return JsonResponse({"error": "User not found"}, status=404)

    if not (current_user.is_superadmin or current_user.is_hr):
        return JsonResponse(
            {"error": "You don't have permission to get the managers list"},
            status=403
        )

    try:
        managers = User.objects.filter(is_manager=True).select_related("employee")

        response_list = []

        for manager in managers:
            emp = manager.employee

            image_url = (
                request.build_absolute_uri(manager.image.url)
                if manager.image else None
            )

            response_list.append({
                "id": manager.id,
                "email": manager.email,
                "name": emp.name if emp else "",
                "empid": emp.empid if emp else "",
                "image_url": image_url,
                "is_superadmin": manager.is_superadmin,
                "is_hr": manager.is_hr,
                "is_manager": manager.is_manager,
            })

        return JsonResponse({"managers": response_list}, status=200)

    except Exception as e:
        return JsonResponse(
            {"error": f"Internal server error: {str(e)}"},
            status=500
        )
    
@swagger_auto_schema(
    method="get",    
    operation_summary="Get Manager Employees",
    manual_parameters=[
        openapi.Parameter(
            "Authorization",
            openapi.IN_HEADER,
            type=openapi.TYPE_STRING,
            required=True,
        )
    ],
    tags=["Manager"],
)
@api_view(["GET"])
@permission_classes([JWTAuthenticationPermission,IsManager])
def get_manager_employees(request, id):

    current_user = request.user_obj
    if request.method != "GET":
        return JsonResponse({"error": "GET request required"}, status=400)

    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        return JsonResponse({"error": "Authorization missing"}, status=401)

    token = auth.split(" ")[1]
    payload = decode_access_token(token)
    if not payload:
        return JsonResponse({"error": "Invalid token"}, status=401)

    current_user = User.objects.filter(email=payload.get("sub")).first()
    if not current_user:
        return JsonResponse({"error": "User not found"}, status=404)

    if not (current_user.is_superadmin or current_user.is_hr or current_user.is_manager):
        return JsonResponse(
            {"error": "Don't have permission to get the manager's employees list"},
            status=403
        )

    serializer = GetManagerEmployeesSerializer(data={"empid": id})
    if not serializer.is_valid():
        return JsonResponse(serializer.errors, status=400)

    empid = serializer.validated_data["empid"]

    try:
        manager_user = User.objects.filter(
            employee__empid=empid,
            is_manager=True
        ).first()

        if not manager_user:
            return JsonResponse({"error": "Manager not found"}, status=404)

        mappings = EmployeeManagerMap.objects.filter(manager=manager_user)

        employee_list = []

        for m in mappings:
            emp = m.employee
            user = User.objects.filter(employee=emp).first()

            image_url = (
                request.build_absolute_uri(user.image.url)
                if user and user.image else None
            )

            employee_list.append({
                "id": emp.id,
                "empid": emp.empid,
                "name": emp.name,
                "email": emp.email,
                "image_url": image_url
            })

        return JsonResponse(employee_list, safe=False, status=200)

    except Exception as e:
        return JsonResponse(
            {"error": f"Internal server error: {str(e)}"},
            status=500
        )

