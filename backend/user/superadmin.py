# from django.db import IntegrityError
# from django.contrib.auth.hashers import make_password
# from .models import User

# def create_superadmin():
#     email = "superadmin@gmail.com"
#     password = "superadmin"

#     try:
#         existing_user = User.objects.filter(email=email).first()

#         if existing_user:
#             print("Superadmin already exists.")
#             return

#         User.objects.create(
#             email=email,
#             hashed_password=make_password(password),
#             is_superadmin=True,
#             is_hr=False,
#             is_manager=False,
#             is_employee=False
#         )

#         print("Superadmin created successfully.")

#     except IntegrityError:
#         print("Superadmin creation failed due to Integrity Error.")
