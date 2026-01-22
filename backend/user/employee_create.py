# import random
# import string
# from django.contrib.auth.hashers import make_password
# from django.db import transaction
# from .models import User, Employee, EmployeeManagerMap


# def create_employee_logic(name, email, empid,
#                           is_superadmin=False,
#                           is_hr=False,
#                           is_manager=False,
#                         #   manager_email=None):

#     password = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
#     hashed_password = make_password(password)

#     with transaction.atomic():

#         employee_obj = Employee.objects.create(
#             empid=empid,
#             password=hashed_password,
#             name=name,
#             email=email
#         )

#         user_obj = User.objects.create(
#             email=email,
#             hashed_password=hashed_password,
#             is_superadmin=is_superadmin,
#             is_hr=is_hr,
#             is_manager=is_manager,
#             is_employee=not (is_superadmin or is_hr or is_manager),
#             employee=employee_obj
#         )

#         if manager_email:
#             manager_user = User.objects.filter(email=manager_email, is_manager=True).first()
#             if manager_user:
#                 EmployeeManagerMap.objects.create(
#                     employee=employee_obj,
#                     manager=manager_user
#                 )

#     return {
#         "password": password,
#         "empid": empid,
#         "email": email
#     }
