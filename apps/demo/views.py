from django.conf import settings
from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .services import demo_user_create


class DemoTokenSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()


class DemoLoginView(APIView):
    """Create a throwaway demo account with sample data and log in as it."""

    permission_classes = [permissions.AllowAny]
    # A stale token from a previous visit must not get in the way of starting a new demo.
    authentication_classes = []
    # Every call creates a user, so keep it to a few per visitor.
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "demo"

    @extend_schema(request=None, responses={201: DemoTokenSerializer})
    def post(self, request):
        if not settings.DEMO_ENABLED:
            raise NotFound(_("The demo is not available."))
        refresh = RefreshToken.for_user(demo_user_create())
        data = {"access": str(refresh.access_token), "refresh": str(refresh)}
        return Response(DemoTokenSerializer(data).data, status=status.HTTP_201_CREATED)
