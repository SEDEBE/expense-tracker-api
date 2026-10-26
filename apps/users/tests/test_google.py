import pytest
from django.urls import reverse

from apps.users.models import User
from apps.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

URL = reverse("users:google-login")
ME_URL = reverse("users:me")
TOKEN_URL = reverse("users:token-obtain")
REFRESH_URL = reverse("users:token-refresh")
CLAIMS = {
    "email": "ana@gmail.com",
    "email_verified": True,
    "given_name": "Ana",
    "family_name": "García",
}


@pytest.fixture(autouse=True)
def google_enabled(settings):
    settings.GOOGLE_CLIENT_ID = "test-client-id.apps.googleusercontent.com"


@pytest.fixture
def google_says(monkeypatch):
    """Replace the call to Google with fixed claims (or an error)."""

    def configure(claims=None, error=None):
        def fake_verify(credential, transport, audience):
            assert audience == "test-client-id.apps.googleusercontent.com"
            if error:
                raise error
            return claims

        monkeypatch.setattr("apps.users.google.id_token.verify_oauth2_token", fake_verify)

    return configure


def test_signs_up_a_new_user(api_client, google_says):
    google_says(CLAIMS)

    response = api_client.post(URL, {"credential": "token"}, HTTP_ACCEPT_LANGUAGE="es")

    assert response.status_code == 200
    user = User.objects.get(email="ana@gmail.com")
    assert (user.first_name, user.last_name, user.language) == ("Ana", "García", "es")
    assert not user.has_usable_password()


def test_returns_tokens_that_work(api_client, google_says):
    google_says(CLAIMS)
    access = api_client.post(URL, {"credential": "token"}).data["access"]

    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    assert api_client.get(ME_URL).data["email"] == "ana@gmail.com"


def test_logs_in_an_existing_verified_user_with_the_same_email(api_client, google_says):
    existing = UserFactory(email="Ana@gmail.com", email_verified=True)
    google_says(CLAIMS)

    api_client.post(URL, {"credential": "token"})

    assert User.objects.count() == 1
    existing.refresh_from_db()
    assert existing.has_usable_password()  # their password still works


def test_takes_an_unverified_account_back_from_whoever_set_its_password(api_client, google_says):
    # Someone signed up with Ana's address before she ever used the app ("pre-account takeover").
    UserFactory(email="ana@gmail.com")
    squatter = api_client.post(TOKEN_URL, {"email": "ana@gmail.com", "password": "S3cure-pass!"})
    google_says(CLAIMS)

    response = api_client.post(URL, {"credential": "token"})

    assert response.status_code == 200
    user = User.objects.get(email="ana@gmail.com")
    assert user.email_verified
    assert not user.has_usable_password()
    # The squatter's password and session stop working.
    login = api_client.post(TOKEN_URL, {"email": "ana@gmail.com", "password": "S3cure-pass!"})
    assert login.status_code == 401
    refresh = api_client.post(REFRESH_URL, {"refresh": squatter.data["refresh"]})
    assert refresh.status_code == 401
    # Ana's own new session works.
    assert api_client.post(REFRESH_URL, {"refresh": response.data["refresh"]}).status_code == 200


def test_new_google_users_are_verified(api_client, google_says):
    google_says(CLAIMS)

    api_client.post(URL, {"credential": "token"})

    assert User.objects.get(email="ana@gmail.com").email_verified


def test_rejects_an_invalid_token(api_client, google_says):
    google_says(error=ValueError("Token expired"))

    response = api_client.post(URL, {"credential": "token"})

    assert response.status_code == 401
    assert not User.objects.exists()


def test_rejects_an_unverified_email(api_client, google_says):
    google_says({**CLAIMS, "email_verified": False})

    assert api_client.post(URL, {"credential": "token"}).status_code == 401


def test_rejects_a_disabled_account(api_client, google_says):
    UserFactory(email="ana@gmail.com", is_active=False)
    google_says(CLAIMS)

    assert api_client.post(URL, {"credential": "token"}).status_code == 401


def test_requires_a_credential(api_client):
    assert api_client.post(URL, {}).status_code == 400


def test_returns_404_when_not_configured(api_client, settings):
    settings.GOOGLE_CLIENT_ID = ""

    assert api_client.post(URL, {"credential": "token"}).status_code == 404
