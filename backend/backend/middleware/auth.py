from django.utils.deprecation import MiddlewareMixin
from user.utils.auth import decode_token
from user.models import User

class AuthMiddleware(MiddlewareMixin):
    def process_request(self, request):
        token = request.headers.get("Authorization")

        if token and token.startswith("Bearer "):
            token = token.split(" ")[1]
            payload = decode_token(token)

            if payload:
                email = payload.get("email")
                user = User.objects.filter(email=email).first()
                request.current_user = user
            else:
                request.current_user = None
        else:
            request.current_user = None
