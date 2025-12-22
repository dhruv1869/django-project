from django.urls import path
from .views import create_leave_balance, apply_leave, get_my_leaves, get_leave_by_id, get_all_leaves

urlpatterns = [
    path("create_leave_balance/", create_leave_balance),
    path("apply_leave/",apply_leave ),
    path("my-leaves/", get_my_leaves),
    path("leave/<int:leave_id>/", get_leave_by_id),
    path("all-leaves/", get_all_leaves),
]
