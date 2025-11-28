import os
import jwt
from datetime import datetime, timedelta, timezone
from django.conf import settings
from django.contrib.auth.hashers import make_password, check_password
from jose import JWTError

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = "HS256"
EXPIRE_TIME = getattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 60)

# =============================
#     PASSWORD HASH / VERIFY
# =============================
def hash_password(password: str):
    return make_password(password)

def verify_password(password: str, hashed_password: str):
    return check_password(password, hashed_password)

# =============================
#     CREATE TOKEN (JWT)
# =============================
def create_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=EXPIRE_TIME)
    to_encode["exp"] = expire
    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return token if isinstance(token, str) else token.decode("utf-8")

# =============================
#     DECODE TOKEN
# =============================
def decode_access_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
