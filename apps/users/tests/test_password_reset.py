import re

import pytest
from django.urls import reverse

from apps.users.models import User
from apps.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

REQUEST_URL = reverse("users:password-reset")
CONFIRM_URL = reverse("users:password-reset-confirm")
TOKEN_URL = reverse("users:token-obtain")
NEW_PASSWORD = "Otra-clave-segura-42"


def confirm(client, uid, token, password=NEW_PASSWORD):
    return client.post(CONFIRM_URL, {"uid": uid, "token": token, "password": password})


def link_parts(email_body):
    match = re.search(r"/restablecer\?uid=([^&\s]+)&token=([^\s]+)", email_body)
    assert match, email_body
    return match.group(1), match.group(2)


class TestRequest:
    def test_emails_a_reset_link_in_the_users_language(self, api_client, mailoutbox, settings):
        settings.FRONTEND_URL = "https://gastos.example.com"
        user = UserFactory(email="ana@example.com", language="es")

        response = api_client.post(REQUEST_URL, {"email": "ANA@example.com"})

        assert response.status_code == 202
        assert len(mailoutbox) == 1
        email = mailoutbox[0]
        assert email.to == [user.email]
        assert email.subject == "Restablece tu contraseña"
        assert "https://gastos.example.com/restablecer?uid=" in email.body

    def test_answers_the_same_for_an_unknown_email(self, api_client, mailoutbox):
        UserFactory(email="ana@example.com")

        known = api_client.post(REQUEST_URL, {"email": "ana@example.com"})
        unknown = api_client.post(REQUEST_URL, {"email": "nadie@example.com"})

        assert unknown.status_code == known.status_code == 202
        assert unknown.data == known.data
        assert len(mailoutbox) == 1

    def test_skips_demo_and_inactive_accounts(self, api_client, mailoutbox):
        UserFactory(email="demo-1@demo.invalid", is_demo=True)
        UserFactory(email="old@example.com", is_active=False)

        api_client.post(REQUEST_URL, {"email": "demo-1@demo.invalid"})
        api_client.post(REQUEST_URL, {"email": "old@example.com"})

        assert mailoutbox == []

    def test_rejects_an_invalid_email(self, api_client):
        assert api_client.post(REQUEST_URL, {"email": "no-es-un-email"}).status_code == 400


class TestConfirm:
    def request_link(self, api_client, mailoutbox, user):
        api_client.post(REQUEST_URL, {"email": user.email})
        return link_parts(mailoutbox[-1].body)

    def test_sets_the_new_password(self, api_client, mailoutbox):
        user = UserFactory(email="ana@example.com")
        uid, token = self.request_link(api_client, mailoutbox, user)

        response = confirm(api_client, uid, token)

        assert response.status_code == 204
        login = api_client.post(TOKEN_URL, {"email": "ana@example.com", "password": NEW_PASSWORD})
        assert login.status_code == 200

    def test_a_link_works_only_once(self, api_client, mailoutbox):
        user = UserFactory()
        uid, token = self.request_link(api_client, mailoutbox, user)
        confirm(api_client, uid, token)

        again = confirm(api_client, uid, token, "Y-otra-mas-77")

        assert again.status_code == 400
        assert "detail" in again.data

    def test_rejects_a_wrong_token(self, api_client, mailoutbox):
        user = UserFactory()
        uid, _ = self.request_link(api_client, mailoutbox, user)

        response = confirm(api_client, uid, "a-bad-token")

        assert response.status_code == 400

    def test_rejects_a_malformed_uid(self, api_client):
        response = confirm(api_client, "@@", "x")

        assert response.status_code == 400

    def test_applies_the_password_validators(self, api_client, mailoutbox):
        user = UserFactory()
        uid, token = self.request_link(api_client, mailoutbox, user)

        response = confirm(api_client, uid, token, "123")

        assert response.status_code == 400
        assert "password" in response.data
        user.refresh_from_db()
        assert user.check_password("S3cure-pass!")

    def test_lets_a_google_user_set_a_password(self, api_client, mailoutbox):
        user = User.objects.create(email="g@example.com")
        user.set_unusable_password()
        user.save()
        uid, token = self.request_link(api_client, mailoutbox, user)

        response = confirm(api_client, uid, token)

        assert response.status_code == 204
