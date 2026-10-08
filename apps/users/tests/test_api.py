import pytest
from django.urls import reverse

from apps.users.models import User

pytestmark = pytest.mark.django_db

REGISTER_URL = reverse("users:register")
TOKEN_URL = reverse("users:token-obtain")
REFRESH_URL = reverse("users:token-refresh")
ME_URL = reverse("users:me")


class TestRegister:
    def test_creates_user(self, api_client):
        payload = {"email": "ana@example.com", "password": "S3cure-pass!", "first_name": "Ana"}

        response = api_client.post(REGISTER_URL, payload)

        assert response.status_code == 201
        assert response.data["email"] == "ana@example.com"
        assert "password" not in response.data
        assert User.objects.filter(email="ana@example.com").exists()

    def test_rejects_weak_password(self, api_client):
        response = api_client.post(REGISTER_URL, {"email": "a@example.com", "password": "123"})

        assert response.status_code == 400
        assert "password" in response.data

    def test_rejects_duplicate_email(self, api_client, user):
        response = api_client.post(REGISTER_URL, {"email": user.email, "password": "S3cure-pass!"})

        assert response.status_code == 400
        assert "email" in response.data


class TestJwtFlow:
    def test_login_refresh_and_access_protected_endpoint(self, api_client, user):
        tokens = api_client.post(TOKEN_URL, {"email": user.email, "password": "S3cure-pass!"})
        assert tokens.status_code == 200

        refreshed = api_client.post(REFRESH_URL, {"refresh": tokens.data["refresh"]})
        assert refreshed.status_code == 200

        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refreshed.data['access']}")
        me = api_client.get(ME_URL)
        assert me.status_code == 200
        assert me.data["email"] == user.email

    def test_login_with_wrong_password_fails(self, api_client, user):
        response = api_client.post(TOKEN_URL, {"email": user.email, "password": "wrong"})

        assert response.status_code == 401


class TestMe:
    def test_requires_authentication(self, api_client):
        assert api_client.get(ME_URL).status_code == 401

    def test_updates_name_but_not_email(self, auth_client, user):
        response = auth_client.patch(
            ME_URL, {"first_name": "New", "email": "hacker@example.com"}, format="json"
        )

        assert response.status_code == 200
        user.refresh_from_db()
        assert user.first_name == "New"
        assert user.email != "hacker@example.com"
