from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    GoogleLoginView,
    LoginView,
    MeView,
    PasswordResetConfirmView,
    PasswordResetView,
    RegisterView,
)

app_name = "users"

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("token/", LoginView.as_view(), name="token-obtain"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("google/", GoogleLoginView.as_view(), name="google-login"),
    path("password-reset/", PasswordResetView.as_view(), name="password-reset"),
    path(
        "password-reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),
    path("me/", MeView.as_view(), name="me"),
]
