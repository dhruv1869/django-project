import json, random, string, os
from uuid import uuid4
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .utils.auth import verify_password, create_token, hash_password ,decode_access_token
from .models import User, Employee, EmployeeManagerMap
from django.contrib.auth.hashers import check_password, make_password
import shutil
from django.http.multipartparser import MultiPartParser

ALLOWED_IMAGE_TYPES = ["image/png", "image/jpeg", "image/jpg"]
UPLOAD_FOLDER = os.path.join(settings.MEDIA_ROOT, "employees")

PHOTOS_BASE_PATH = os.path.join(settings.MEDIA_ROOT, "employees")

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
        return JsonResponse({"error": "Only SuperAdmin, HR, or Manager can create users"}, status=403)

    if current_user.is_manager:
        if request.POST.get("is_superadmin") == "true":
            return JsonResponse({"error": "Manager cannot create SuperAdmin"}, status=403)

    try:
        name = request.POST.get("username")
        email = request.POST.get("email")
        empid = request.POST.get("empid")
        is_superadmin = request.POST.get("is_superadmin") == "true"
        is_hr = request.POST.get("is_hr") == "true"
        is_manager = request.POST.get("is_manager") == "true"
        manager_email = request.POST.get("manager_email")
        file = request.FILES.get("file")

        if not name or not email or not empid or not file:
            return JsonResponse({"error": "Missing required fields"}, status=400)

        if file.content_type not in ALLOWED_IMAGE_TYPES:
            return JsonResponse({"error": "Invalid image type"}, status=400)

        if Employee.objects.filter(empid=empid).exists():
            return JsonResponse({"error": "Employee ID already exists"}, status=400)

        if Employee.objects.filter(email=email).exists():
            return JsonResponse({"error": "Email already exists"}, status=400)

        password = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
        hashed = hash_password(password)

        employee = Employee.objects.create(
            empid=empid,
            name=name,
            email=email,
            password=hashed
        )

        user = User.objects.create(
            email=email,
            hashed_password=hashed,
            is_superadmin=is_superadmin,
            is_hr=is_hr,
            is_manager=is_manager,
            is_employee=True,
            employee=employee
        )

        if manager_email:
            manager = User.objects.filter(email=manager_email, is_manager=True).first()
            if not manager:
                return JsonResponse({"error": "Invalid manager email"}, status=400)

            if manager.email == email:
                return JsonResponse({"error": "User cannot be own manager"}, status=400)

            EmployeeManagerMap.objects.create(employee=employee, manager=manager)

        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        emp_dir = os.path.join(UPLOAD_FOLDER, empid)
        os.makedirs(emp_dir, exist_ok=True)

        ext = os.path.splitext(file.name)[1]
        filename = f"{uuid4().hex}{ext}"
        filepath = os.path.join(emp_dir, filename)

        with open(filepath, "wb") as f:
            for chunk in file.chunks():
                f.write(chunk)

        return JsonResponse({
            "message": "Employee created successfully",
            "username": name,
            "email": email,
            "empid": empid,
            "password": password,
            "user_id": user.id
        })

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
def login_user(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=400)

    try:
        data = json.loads(request.body)

        email = data.get("email")
        password = data.get("password")

        if not email or not password:
            return JsonResponse({"error": "Email and password required"}, status=400)

        user = User.objects.filter(email=email).first()

        if not user:
            return JsonResponse({"error": "Invalid email/password"}, status=401)

        if not verify_password(password, user.hashed_password):
            return JsonResponse({"error": "Invalid email/password"}, status=401)

        token = create_token({"sub": user.email})

        return JsonResponse({
            "username": user.email,
            "access_token": token,
            "token_type": "bearer"
        })

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)




def to_bool(v):
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    return str(v).strip().lower() in ["true", "1", "yes"]


@csrf_exempt
def get_employees(request):
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

    is_superadmin = to_bool(current_user.is_superadmin)
    is_hr = to_bool(current_user.is_hr)
    is_manager = to_bool(current_user.is_manager)
    is_employee = to_bool(current_user.is_employee)

    if is_manager:
        role = "manager"
    elif is_superadmin:
        role = "superadmin"
    elif is_hr:
        role = "hr"
    else:
        role = "employee" 

    if role == "employee":
        return JsonResponse({"error": "You don't have permission to get employees details."}, status=403)

    try:
        if role == "manager":
            mapping = EmployeeManagerMap.objects.filter(manager=current_user)
            employee_ids = [m.employee.id for m in mapping]

            employees = Employee.objects.filter(id__in=employee_ids).values(
                "id", "empid", "name", "email"
            )

        else:
            employees = Employee.objects.all().values(
                "id", "empid", "name", "email"
            )

        if not employees:
            return JsonResponse({"error": "No employees found"}, status=404)

        enriched = []
        for emp in employees:
            empid = str(emp["empid"])
            folder = os.path.join(PHOTOS_BASE_PATH, empid)
            photos = []

            if os.path.isdir(folder):
                for file in os.listdir(folder):
                    if file.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                        photos.append(
                            request.build_absolute_uri(
                                f"/media/employees/{empid}/{file}"
                            )
                        )

            emp["photoUrl"] = photos
            enriched.append(emp)

        return JsonResponse({"employees": enriched}, safe=False)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
    
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

    is_superadmin = to_bool(current_user.is_superadmin)
    is_hr = to_bool(current_user.is_hr)
    is_manager = to_bool(current_user.is_manager)

    if not (is_superadmin or is_hr or is_manager):
        return JsonResponse({"error": "You don't have permission to get employee details."}, status=403)

    try:
        emp_obj = Employee.objects.filter(empid=id).first()
        if not emp_obj:
            return JsonResponse({"error": "Employee not found"}, status=404)

        employee = {
            "id": emp_obj.id,
            "empid": emp_obj.empid,
            "name": emp_obj.name,
            "email": emp_obj.email
        }

        if is_manager:
            is_managed = EmployeeManagerMap.objects.filter(
                manager=current_user,
                employee=emp_obj
            ).exists()

            if not is_managed:
                return JsonResponse({"error": "You don't have access to this employee's details."}, status=403)

        emp_id = str(emp_obj.empid)
        photo_dir = os.path.join(PHOTOS_BASE_PATH, emp_id)

        photo_urls = []
        if os.path.isdir(photo_dir):
            for file in os.listdir(photo_dir):
                if file.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                    photo_urls.append(
                        request.build_absolute_uri(
                            f"/media/employees/{emp_id}/{file}"
                        )
                    )

        employee["photos"] = photo_urls

        return JsonResponse({"employee": employee}, safe=False)

    except Exception as e:
        return JsonResponse({"error": f"Internal server error: {str(e)}"}, status=500)


@csrf_exempt
def update_employee(request):
    if request.method != "PATCH":
        return JsonResponse({"error": "PATCH required"}, status=400)

    from django.http.multipartparser import MultiPartParser
    from django.conf import settings

    parser = MultiPartParser(request.META, request, request.upload_handlers)
    data, files = parser.parse()

    token = request.headers.get("Authorization")
    if not token or not token.startswith("Bearer "):
        return JsonResponse({"error": "Authorization header missing"}, status=401)

    token = token.split(" ")[1]
    payload = decode_access_token(token)

    if not payload:
        return JsonResponse({"error": "Invalid token"}, status=401)

    current_user = User.objects.filter(email=payload.get("sub")).first()
    if not current_user:
        return JsonResponse({"error": "User not found"}, status=404)

    if not (current_user.is_superadmin or current_user.is_hr):
        return JsonResponse({"error": "Only superadmin or HR can update employees"}, status=403)

    empid = data.get("empid")
    name = data.get("name")
    email = data.get("email")

    is_superadmin = data.get("is_superadmin")
    is_hr = data.get("is_hr")
    is_manager = data.get("is_manager")
    manager_email = data.get("manager_email")

    file = files.get("file")

    if not empid:
        return JsonResponse({"error": "empid is required"}, status=400)

    employee_obj = Employee.objects.filter(empid=empid).first()
    if not employee_obj:
        return JsonResponse({"error": "Employee not found"}, status=404)

    user = User.objects.filter(employee=employee_obj).first()

    try:
        if name:
            employee_obj.name = name
        if email:
            if Employee.objects.filter(email=email).exclude(empid=empid).exists():
                return JsonResponse({"error": "Email already exists"}, status=400)
            employee_obj.email = email
        employee_obj.save()

        if email:
            user.email = email
        if is_superadmin:
            user.is_superadmin = (is_superadmin == "true")
        if is_hr:
            user.is_hr = (is_hr == "true")
        if is_manager:
            user.is_manager = (is_manager == "true")

        user.save()

        if file:
            emp_dir = os.path.join(UPLOAD_FOLDER, empid)
            os.makedirs(emp_dir, exist_ok=True)
            ext = os.path.splitext(file.name)[1]
            filename = f"{uuid4().hex}{ext}"
            filepath = os.path.join(emp_dir, filename)

            with open(filepath, "wb") as f:
                for chunk in file.chunks():
                    f.write(chunk)

        return JsonResponse({"message": "Employee updated", "empid": empid})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def change_password(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    try:
        data = request.POST  

        old_password = data.get("old_password")
        new_password = data.get("new_password")
        email = data.get("email")

        if not email or not old_password or not new_password:
            return JsonResponse({"error": "Missing fields"}, status=400)

        user = User.objects.filter(email=email).first()
        if not user:
            return JsonResponse({"error": "User not found"}, status=404)

        if not check_password(old_password, user.hashed_password):
            return JsonResponse({"error": "Incorrect old password"}, status=401)

        if check_password(new_password, user.hashed_password):
            return JsonResponse({"error": "New password must be different"}, status=400)

        hashed_password = make_password(new_password)

        if user.is_employee:
            emp = Employee.objects.filter(email=email).first()
            if emp:
                emp.password = hashed_password
                emp.save()

        user.hashed_password = hashed_password
        user.save()

        return JsonResponse({"message": "Password changed successfully"}, status=200)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

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
        return JsonResponse({"error": "Only Superadmin or HR can delete an employee"}, status=403)

    try:
        employee = Employee.objects.filter(empid=empid).first()
        if not employee:
            return JsonResponse({"error": "Employee not found"}, status=404)

        user = User.objects.filter(employee=employee).first()

        if user:
            if user.is_superadmin:
                return JsonResponse({"error": "Cannot delete a Superadmin"}, status=403)

            if user.is_hr and not current_user.is_superadmin:
                return JsonResponse({"error": "Only Superadmin can delete an HR"}, status=403)

            if user.id == current_user.id:
                return JsonResponse({"error": "You cannot delete yourself"}, status=403)

            user.delete()

        employee.delete()

        emp_dir = os.path.join(UPLOAD_FOLDER, str(empid))
        if os.path.exists(emp_dir):
            shutil.rmtree(emp_dir)

        return JsonResponse({"message": "Employee and associated user deleted successfully"})

    except Exception as e:
        return JsonResponse({"error": f"Internal server error: {str(e)}"}, status=500)


@csrf_exempt
def add_photo(request, id):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=400)

    token = request.headers.get("Authorization")
    if not token or not token.startswith("Bearer "):
        return JsonResponse({"error": "Authorization header missing"}, status=401)

    token = token.split(" ")[1]
    payload = decode_access_token(token)
    if not payload:
        return JsonResponse({"error": "Invalid token"}, status=401)

    current_user = User.objects.filter(email=payload.get("sub")).first()
    if not current_user:
        return JsonResponse({"error": "User not found"}, status=404)

    if not (current_user.is_superadmin or current_user.is_hr or current_user.is_manager):
        return JsonResponse({"error": "You don't have permission to add it."}, status=403)

    parser = MultiPartParser(request.META, request, request.upload_handlers)
    data, files = parser.parse()

    file = files.get("file")
    if not file:
        return JsonResponse({"error": "File is required"}, status=400)

    employee_obj = Employee.objects.filter(empid=id).first()
    if not employee_obj:
        return JsonResponse({"error": "Employee not found"}, status=404)

    if current_user.is_manager:
        is_managed = EmployeeManagerMap.objects.filter(
            manager=current_user,
            employee=employee_obj
        ).exists()

        if not is_managed:
            return JsonResponse(
                {"error": "You don't have access to this employee's details."},
                status=403
            )

    if file.content_type not in ALLOWED_IMAGE_TYPES:
        return JsonResponse(
            {"error": f"Unsupported file type: {file.name} ({file.content_type})"},
            status=400,
        )

    emp_dir = os.path.join(UPLOAD_FOLDER, str(employee_obj.empid))
    os.makedirs(emp_dir, exist_ok=True)

    ext = os.path.splitext(file.name)[1]
    filename = f"{uuid4().hex}{ext}"
    filepath = os.path.join(emp_dir, filename)

    with open(filepath, "wb") as f:
        for chunk in file.chunks():
            f.write(chunk)

    photo_url = request.build_absolute_uri(f"/media/{employee_obj.empid}/{filename}")

    return JsonResponse({"photo_url": photo_url})


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
        return JsonResponse({"error": "You don't have permission to get photos"}, status=403)

    try:
        employee = Employee.objects.filter(empid=empid).first()
        if not employee:
            return JsonResponse({"error": "Employee not found"}, status=404)

        if current_user.is_manager:
            is_managed = EmployeeManagerMap.objects.filter(
                manager=current_user,
                employee=employee
            ).exists()

            if not is_managed:
                return JsonResponse({"error": "You don't have access to this employee's details"}, status=403)

        emp_folder = os.path.join(PHOTOS_BASE_PATH, empid)
        photo_urls = []

        if os.path.isdir(emp_folder):
            for file in os.listdir(emp_folder):
                if file.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                    url = request.build_absolute_uri(
                        f"/media/employees/{empid}/{file}"
                    )
                    photo_urls.append(url)

        return JsonResponse({"urls": photo_urls})

    except Exception as e:
        return JsonResponse({"error": f"Internal server error: {str(e)}"}, status=500)


@csrf_exempt
def delete_photo(request, id):
    if request.method != "DELETE":
        return JsonResponse({"error": "Invalid request method"}, status=405)

    try:
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
            return JsonResponse({"error": "You don't have permission to delete photos."}, status=403)

        try:
            employee_obj = Employee.objects.get(empid=id)
        except Employee.DoesNotExist:
            return JsonResponse({"error": "Employee not found"}, status=404)

        if current_user.is_manager:
            is_managed = EmployeeManagerMap.objects.filter(
                manager=current_user,
                employee=employee_obj
            ).exists()

            if not is_managed:
                return JsonResponse(
                    {"error": "You don't have access to this employee's details."},
                    status=403
                )

        emp_dir = os.path.join(UPLOAD_FOLDER, employee_obj.empid)

        if not os.path.exists(emp_dir):
            return JsonResponse({"error": "No photos found"}, status=404)

        photos = [
            f for f in os.listdir(emp_dir)
            if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
        ]

        if len(photos) == 0:
            return JsonResponse({"error": "No photos found"}, status=404)

        if len(photos) <= 1:
            return JsonResponse({"error": "At least one photo must remain."}, status=400)

        photo_to_delete = photos[0]
        path_to_delete = os.path.join(emp_dir, photo_to_delete)

        os.remove(path_to_delete)

        return JsonResponse({"message": f"Photo '{photo_to_delete}' deleted successfully"})

    except Exception as e:
        return JsonResponse({"error": f"Internal server error: {str(e)}"}, status=500)
    
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

            response_list.append({
                "id": manager.id,
                "email": manager.email,
                "name": emp.name if emp else "",
                "empid": emp.empid if emp else "",
                "is_superadmin": manager.is_superadmin,
                "is_hr": manager.is_hr,
                "is_manager": manager.is_manager,
            })

        return JsonResponse({"managers": response_list}, safe=False)

    except Exception as e:
        return JsonResponse({"error": f"Internal server error: {str(e)}"}, status=500)

@csrf_exempt
def get_manager_employees(request, id):
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
            {"error": "Don't have permission to get the managers list"},
            status=403
        )

    try:
        manager_user = User.objects.filter(
            employee__empid=id,
            is_manager=True
        ).first()

        if not manager_user:
            return JsonResponse({"error": "Manager not found"}, status=404)

        mappings = EmployeeManagerMap.objects.filter(manager=manager_user)
        employees = [m.employee for m in mappings]

        employee_list = []
        for emp in employees:
            employee_list.append({
                "id": emp.id,
                "empid": emp.empid,
                "name": emp.name,
                "email": emp.email
            })

        return JsonResponse(employee_list, safe=False, status=200)

    except Exception as e:
        return JsonResponse(
            {"error": f"Internal server error: {str(e)}"},
            status=500
        )


