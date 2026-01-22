from django.urls import path
from .views import create_user, login_user, get_employees, get_employee_by_id , change_password, delete_employee, get_employee_photos, update_employee , add_photo , delete_photo, get_managers , get_manager_employees

urlpatterns = [
    path('create/', create_user,name="create-user"),
    path('login/', login_user,name="login-user"),
    path('get/', get_employees, name="get-employees"),
    path('get_by_id/<str:id>/', get_employee_by_id, name="get-employee-by-id"),
    path('update-employee/', update_employee, name="update-employee"),
    path('change-password/', change_password, name="change-password"),
    path('delete/<str:empid>/', delete_employee, name="delete-employee"),
    path('addphoto/<str:id>/', add_photo, name="add-photo"),
    path('photos/<str:empid>/', get_employee_photos, name="get-employee-photos"),
    path("deletephoto/<str:id>/", delete_photo, name="delete-photo"),
    path("managers/", get_managers, name="get-managers"),
    path("manager_employee/<str:id>/", get_manager_employees, name="get-manager-employees"),
]

