import pytest
from django.urls import reverse

from apps.users.models import User

pytestmark = pytest.mark.django_db

URL = reverse("demo-login")
ME_URL = reverse("users:me")


@pytest.fixture(autouse=True)
def demo_enabled(settings):
    settings.DEMO_ENABLED = True


def test_returns_tokens_for_a_new_demo_user(api_client):
    response = api_client.post(URL)

    assert response.status_code == 201
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    me = api_client.get(ME_URL)
    assert me.status_code == 200
    assert me.data["is_demo"] is True
    assert me.data["language"] == "es"


def test_the_demo_user_starts_with_sample_data(api_client):
    access = api_client.post(URL).data["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    assert api_client.get(reverse("expenses:category-list")).data["count"] > 0
    assert api_client.get(reverse("expenses:expense-list")).data["count"] > 0


def test_ignores_a_stale_token(api_client):
    api_client.credentials(HTTP_AUTHORIZATION="Bearer not-a-valid-token")

    assert api_client.post(URL).status_code == 201


def test_returns_404_when_the_demo_is_disabled(api_client, settings):
    settings.DEMO_ENABLED = False

    response = api_client.post(URL)

    assert response.status_code == 404
    assert not User.objects.filter(is_demo=True).exists()


def test_only_accepts_post(api_client):
    assert api_client.get(URL).status_code == 405
