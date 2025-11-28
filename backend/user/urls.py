from django.urls import path
from .views import create_user, login_user

urlpatterns = [
    path('create/', create_user),
    path('login/', login_user),
]
