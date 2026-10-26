import pytest
from django.core.cache import cache
from django.urls import reverse

from apps.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

URL = reverse("admin:login")


@pytest.fixture(autouse=True)
def clear_failures(settings):
    settings.ADMIN_LOGIN_MAX_FAILURES = 3
    cache.clear()
    yield
    cache.clear()


def login(client, password):
    return client.post(URL, {"username": "boss@example.com", "password": password})


@pytest.fixture
def staff():
    return UserFactory(email="boss@example.com", is_staff=True, is_superuser=True)


def test_locks_an_ip_out_after_too_many_failed_logins(client, staff):
    statuses = [login(client, "guess").status_code for _ in range(4)]

    assert statuses == [200, 200, 200, 429]
    # Not even the right password gets in while locked out.
    assert login(client, "S3cure-pass!").status_code == 429


def test_good_logins_are_not_counted(client, staff):
    for _ in range(5):
        assert login(client, "S3cure-pass!").status_code == 302
        client.logout()


def test_the_login_page_still_opens_while_locked_out(client, staff):
    for _ in range(3):
        login(client, "guess")

    assert client.get(URL).status_code == 200
