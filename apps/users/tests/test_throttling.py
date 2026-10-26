import pytest
from django.core.cache import cache
from django.urls import reverse
from rest_framework.throttling import ScopedRateThrottle

from apps.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def rates(monkeypatch):
    # Tests turn these limits off (config/settings/test.py); here they are what is being tested.
    monkeypatch.setitem(ScopedRateThrottle.THROTTLE_RATES, "login", "3/min")
    monkeypatch.setitem(ScopedRateThrottle.THROTTLE_RATES, "register", "2/hour")
    cache.clear()
    yield
    cache.clear()


def test_limits_login_attempts(api_client):
    UserFactory(email="ana@example.com")
    url = reverse("users:token-obtain")
    wrong = {"email": "ana@example.com", "password": "guess"}

    statuses = [api_client.post(url, wrong).status_code for _ in range(4)]

    assert statuses == [401, 401, 401, 429]


def test_limits_sign_ups(api_client):
    url = reverse("users:register")

    statuses = [
        api_client.post(url, {"email": f"u{i}@example.com", "password": "S3cure-pass!"}).status_code
        for i in range(3)
    ]

    assert statuses == [201, 201, 429]


def test_limits_google_logins(api_client, settings):
    settings.GOOGLE_CLIENT_ID = "test-client-id"
    url = reverse("users:google-login")

    statuses = [api_client.post(url, {}).status_code for _ in range(4)]

    assert statuses == [400, 400, 400, 429]
