from django.urls import path
from .views import create_leave_balance, apply_leave, get_my_leaves, get_leave_by_id, get_all_leaves, update_leave_request, update_leave_balance, update_leave_status, get_leave_balance, delete_leave_request, create_holiday, get_holidays, update_holiday

urlpatterns = [
    path("create_leave_balance/", create_leave_balance,name="create-leave-balance"),
    path("apply_leave/",apply_leave,name="apply-leave"),
    path("my-leaves/", get_my_leaves,name="my-leaves"),
    path("leave/<int:leave_id>/", get_leave_by_id,name="leave-by-id"),
    path("all-leaves/", get_all_leaves,name="all-leaves"),
    path("leave_update/<int:leave_id>/", update_leave_request,name="update-leave"),
    path("leave_balance/<str:employee_id>/", update_leave_balance,name="update-leave-balance"),
    path("leave_status/<int:leave_id>/",update_leave_status,name="update-leave-status"),
    path("get_leave_balance/<str:empid>/", get_leave_balance,name="get-leave-balance"),
    path("delete_leave/<int:leave_id>/",delete_leave_request,name="delete-leave"),
    path("create_holiday/",create_holiday,name="Create holiday"),
    path("holidays/", get_holidays, name="get-holidays"),
    path("update_holiday/<int:festival_id>/", update_holiday, name="update-holiday"),
]
