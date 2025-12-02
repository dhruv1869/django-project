from django.urls import path
from .views import create_user, login_user, get_employees, get_employee_by_id , change_password, delete_employee

urlpatterns = [
    path('create/', create_user),
    path('login/', login_user),
    path('get/', get_employees),
    path('get_by_id/<str:id>/', get_employee_by_id),
    path('change-password/', change_password),
    path('delete/<str:empid>/', delete_employee),

]
