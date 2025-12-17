from django.urls import path
from .views import create_user, login_user, get_employees, get_employee_by_id , change_password, delete_employee, get_employee_photos, update_employee , add_photo , delete_photo, get_managers , get_manager_employees

urlpatterns = [
    path('create/', create_user),
    path('login/', login_user),
    path('get/', get_employees),
    path('get_by_id/<str:id>/', get_employee_by_id),
    path('update-employee/', update_employee),
    path('change-password/', change_password),
    path('delete/<str:empid>/', delete_employee),
    path('addphoto/<str:id>/', add_photo),
    path('photos/<str:empid>/', get_employee_photos),
    path("deletephoto/<str:id>/", delete_photo),
    path("managers/", get_managers),
    path("manager_employee/<str:id>/", get_manager_employees),
]

