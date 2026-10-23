from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions, status
from rest_framework.exceptions import AuthenticationFailed, NotFound, ValidationError
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .google import google_token_verify
from .serializers import (
    GoogleLoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetSerializer,
    RegisterSerializer,
    TokenPairSerializer,
    UserSerializer,
)
from .services import (
    password_reset_confirm,
    password_reset_request,
    user_create,
    user_get_or_create_from_google,
)


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(request=RegisterSerializer, responses={201: UserSerializer})
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            # Without an explicit choice, keep the language negotiated from Accept-Language.
            data = {"language": request.LANGUAGE_CODE, **serializer.validated_data}
            user = user_create(**data)
        except DjangoValidationError as exc:
            # Model and password validators raise Django errors; expose them as a normal 400.
            detail = exc.message_dict if hasattr(exc, "error_dict") else {"password": exc.messages}
            raise ValidationError(detail) from exc
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    http_method_names = ["get", "patch"]

    def get_object(self):
        return self.request.user


class GoogleLoginView(APIView):
    """Log in or sign up with a Google account and get the same tokens as /auth/token/."""

    permission_classes = [permissions.AllowAny]

    @extend_schema(request=GoogleLoginSerializer, responses={200: TokenPairSerializer})
    def post(self, request):
        if not settings.GOOGLE_CLIENT_ID:
            raise NotFound(_("Signing in with Google is not available."))
        serializer = GoogleLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            claims = google_token_verify(serializer.validated_data["credential"])
        except ValueError as exc:
            raise AuthenticationFailed(_("Google could not confirm your identity.")) from exc

        user = user_get_or_create_from_google(
            email=claims["email"],
            first_name=claims.get("given_name", "")[:150],
            last_name=claims.get("family_name", "")[:150],
            language=request.LANGUAGE_CODE,
        )
        if not user.is_active:
            raise AuthenticationFailed(_("This account is disabled."))

        refresh = RefreshToken.for_user(user)
        data = {"access": str(refresh.access_token), "refresh": str(refresh)}
        return Response(TokenPairSerializer(data).data)


class PasswordResetView(APIView):
    """Email a link to reset the password. Answers the same whether or not the account exists."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    @extend_schema(request=PasswordResetSerializer, responses={202: dict})
    def post(self, request):
        serializer = PasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        password_reset_request(email=serializer.validated_data["email"])
        message = _("If an account uses that email, we have sent it a link to reset the password.")
        return Response({"detail": message}, status=status.HTTP_202_ACCEPTED)


class PasswordResetConfirmView(APIView):
    """Set a new password with the uid and token from the reset email."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    @extend_schema(request=PasswordResetConfirmSerializer, responses={204: None})
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            password_reset_confirm(**serializer.validated_data)
        except DjangoValidationError as exc:
            detail = exc.message_dict if hasattr(exc, "error_dict") else {"password": exc.messages}
            raise ValidationError(detail) from exc
        return Response(status=status.HTTP_204_NO_CONTENT)
