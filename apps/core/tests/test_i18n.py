import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db

REGISTER_URL = reverse("users:register")


class TestLanguageNegotiation:
    def test_uses_english_by_default(self, api_client):
        response = api_client.post(REGISTER_URL, {})

        assert response.data["email"] == ["This field is required."]
        assert response["Content-Language"] == "en"

    def test_uses_spainsh_when_requested(self, api_client):
        response = api_client.post(REGISTER_URL, {}, HTTP_ACCEPT_LANGUAGE="es-ES,es;q=0.9")

        assert response.data["email"] == ["Este campo es requerido."]
        assert response["Content-Language"] == "es"

    def test_falls_back_to_english_for_unsupported_languages(self, api_client):
        response = api_client.post(REGISTER_URL, {}, HTTP_ACCEPT_LANGUAGE="fr")

        assert response.data["email"] == ["This field is required."]
