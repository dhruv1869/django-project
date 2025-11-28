import json, random, string, os
from uuid import uuid4
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .utils.auth import verify_password, create_token, hash_password ,decode_access_token
from .models import User, Employee, EmployeeManagerMap

ALLOWED_IMAGE_TYPES = ["image/png", "image/jpeg", "image/jpg"]
UPLOAD_FOLDER = os.path.join(settings.MEDIA_ROOT, "employees")

@csrf_exempt
def create_user(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=400)

    token = request.headers.get("Authorization")
    if not token or not token.startswith("Bearer "):
        return JsonResponse({"error": "Authorization header missing"}, status=401)
    token = request.headers.get("Authorization")
    if not token or not token.startswith("Bearer "):
        return JsonResponse({"error": "Authorization header missing"}, status=401)

    token = token.split(" ")[1]
    payload = decode_access_token(token)   # <-- fixed
    if not payload:
        return JsonResponse({"error": "Invalid token"}, status=401)

    current_user_email = payload.get("sub")
    current_user = User.objects.filter(email=current_user_email, is_superadmin=True).first()
    if not current_user:
        return JsonResponse({"error": "Only SuperAdmin can create employees"}, status=403)


    try:
        name = request.POST.get("username")
        email = request.POST.get("email")
        empid = request.POST.get("empid")
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
            is_superadmin=False,
            is_hr=is_hr,
            is_manager=is_manager,
            is_employee=True,
            employee=employee
        )

        if manager_email:
            manager = User.objects.filter(email=manager_email, is_manager=True).first()
            if not manager:
                return JsonResponse({"error": "Invalid manager email"}, status=400)
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

        user = User.objects.filter(email=email, is_superadmin=True).first()
        if not user:
            return JsonResponse({"error": "Invalid email/password or not superadmin"}, status=401)

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
