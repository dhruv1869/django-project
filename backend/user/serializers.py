from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from .models import User, Employee, EmployeeManagerMap
import random, string


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()

class CreateEmployeeSerializer(serializers.Serializer):
    username = serializers.CharField()
    email = serializers.EmailField()
    empid = serializers.CharField()

    is_superadmin = serializers.BooleanField(default=False)
    is_hr = serializers.BooleanField(default=False)
    is_manager = serializers.BooleanField(default=False)
    manager_email = serializers.EmailField(required=False, allow_null=True)

    def validate_empid(self, value):
        if Employee.objects.filter(empid=value).exists():
            raise serializers.ValidationError("Employee ID already exists")
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already exists")
        return value

    def create(self, validated_data):
        password = ''.join(
            random.choices(string.ascii_letters + string.digits, k=6)
        )

        hashed_password = make_password(password)

        employee = Employee.objects.create(
            empid=validated_data["empid"],
            name=validated_data["username"],
            email=validated_data["email"],
            password=hashed_password
        )

        user = User.objects.create(
            email=validated_data["email"],
            hashed_password=hashed_password,
            is_superadmin=validated_data["is_superadmin"],
            is_hr=validated_data["is_hr"],
            is_manager=validated_data["is_manager"],
            is_employee=True,
            employee=employee
        )

        manager_email = validated_data.get("manager_email")
        if manager_email:
            manager = User.objects.filter(
                email=manager_email,
                is_manager=True
            ).first()

            if not manager:
                raise serializers.ValidationError({
                    "manager_email": "Invalid manager email"
                })

            EmployeeManagerMap.objects.create(
                employee=employee,
                manager=manager
            )

        return {
            "user": user,
            "employee": employee,
            "password": password
        }


class EmployeeSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = ["id", "empid", "name", "email", "image_url"]

    def get_image_url(self, obj):
        user = getattr(obj, "user", None)
        if user and user.first() and user.first().image:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(user.first().image.url)
            return user.first().image.url
        return None


class UpdateEmployeeSerializer(serializers.Serializer):
    empid = serializers.CharField()

    name = serializers.CharField(required=False)
    email = serializers.EmailField(required=False)

    is_superadmin = serializers.BooleanField(required=False)
    is_hr = serializers.BooleanField(required=False)
    is_manager = serializers.BooleanField(required=False)
    manager_email = serializers.EmailField(required=False, allow_null=True)

    def validate_email(self, value):
        empid = self.initial_data.get("empid")
        if Employee.objects.filter(email=value).exclude(empid=empid).exists():
            raise serializers.ValidationError("Email already exists")
        return value

class ChangePasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    old_password = serializers.CharField()
    new_password = serializers.CharField(min_length=6)

    def validate(self, attrs):
        if attrs["old_password"] == attrs["new_password"]:
            raise serializers.ValidationError(
                {"new_password": "New password must be different from old password"}
            )
        return attrs

class DeleteEmployeeSerializer(serializers.Serializer):
    empid = serializers.CharField()


class AddPhotoSerializer(serializers.Serializer):
    empid = serializers.CharField()
    file = serializers.ImageField()

    def validate_file(self, file):
        allowed_types = ["image/png", "image/jpeg", "image/jpg", "image/webp"]
        if file.content_type not in allowed_types:
            raise serializers.ValidationError(
                f"Unsupported file type: {file.name} ({file.content_type})"
            )
        return file
    
class GetEmployeePhotosSerializer(serializers.Serializer):
    empid = serializers.CharField()

class DeletePhotoSerializer(serializers.Serializer):
    empid = serializers.CharField()

class GetManagersSerializer(serializers.Serializer):
    # Currently no fields, but keeps consistency and allows future query params
    pass


class GetManagerEmployeesSerializer(serializers.Serializer):
    empid = serializers.CharField()