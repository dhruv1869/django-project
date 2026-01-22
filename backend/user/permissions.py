from rest_framework.permissions import BasePermission
from user.models import User
from user.utils.auth import decode_access_token


class JWTAuthenticationPermission(BasePermission):

    def has_permission(self, request, view):
        auth = request.headers.get("Authorization")

        if not auth or not auth.startswith("Bearer "):
            return False

        token = auth.split(" ")[1]
        payload = decode_access_token(token)

        if not payload:
            return False

        user = User.objects.filter(email=payload.get("sub")).first()
        if not user:
            return False

        request.user_obj = user
        return True


class IsEmployee(BasePermission):
    def has_permission(self, request, view):
        return bool(
            hasattr(request, "user_obj")
            and request.user_obj.is_employee
        )


class IsManager(BasePermission):
    def has_permission(self, request, view):
        return bool(
            hasattr(request, "user_obj")
            and request.user_obj.is_manager
        )


class IsHR(BasePermission):
    def has_permission(self, request, view):
        return bool(
            hasattr(request, "user_obj")
            and request.user_obj.is_hr
        )


class IsHRorSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(
            hasattr(request, "user_obj")
            and (
                request.user_obj.is_hr
                or request.user_obj.is_superadmin
            )
        )


class IsHRManagerAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(
            hasattr(request, "user_obj")
            and (
                request.user_obj.is_hr
                or request.user_obj.is_manager
                or request.user_obj.is_superadmin
            )
        )
