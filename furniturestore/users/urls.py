from django.urls import path
from .views import RegisterAPIView, LoginAPIView, ChangePasswordAPIView, UserListAPIView

urlpatterns = [
    path("register/", RegisterAPIView.as_view(), name="register"),

    path("login/", LoginAPIView.as_view(), name="login"),
    
    path("change-password/", ChangePasswordAPIView.as_view(), name="change-password"),

    path("get-user/", UserListAPIView.as_view(), name="get-user"),
]