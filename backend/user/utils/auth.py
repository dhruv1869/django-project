import os
import jwt
from datetime import datetime, timedelta, timezone
from django.conf import settings
from django.contrib.auth.hashers import make_password, check_password
from jose import JWTError
from django.http import JsonResponse
from user.models import User

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = "HS256"
EXPIRE_TIME = getattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 60)

def hash_password(password: str):
    return make_password(password)

def verify_password(password: str, hashed_password: str):
    return check_password(password, hashed_password)

def create_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=EXPIRE_TIME)
    to_encode["exp"] = expire
    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return token if isinstance(token, str) else token.decode("utf-8")

def decode_access_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

def get_user_from_request(request):
    auth = request.headers.get("Authorization")

    if not auth or not auth.startswith("Bearer "):
        return None, JsonResponse(
            {"error": "Authorization missing"}, status=401
        )

    token = auth.split(" ")[1]
    payload = decode_access_token(token)

    if not payload:
        return None, JsonResponse(
            {"error": "Invalid token"}, status=401
        )

    user = User.objects.filter(email=payload.get("sub")).first()
    if not user:
        return None, JsonResponse(
            {"error": "User not found"}, status=404
        )

    return user, None

# utils/auth.py

def authenticate_request(request):
    auth = request.headers.get("Authorization")

    if not auth or not auth.startswith("Bearer "):
        return None, JsonResponse(
            {"error": "Authorization missing"}, status=401
        )

    token = auth.split(" ")[1]
    payload = decode_access_token(token)

    if not payload:
        return None, JsonResponse(
            {"error": "Invalid token"}, status=401
        )

    user = User.objects.filter(email=payload.get("sub")).first()
    if not user:
        return None, JsonResponse(
            {"error": "User not found"}, status=404
        )

    return user, None

