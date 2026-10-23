import pytest
from django.urls import reverse

FRONTEND = "http://localhost:5173"


@pytest.fixture(autouse=True)
def allowed_origins(settings):
    settings.CORS_ALLOWED_ORIGINS = [FRONTEND]


def preflight(client, origin):
    return client.options(
        reverse("health"),
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )


def test_preflight_from_allowed_origin_is_accepted(api_client):
    response = preflight(api_client, FRONTEND)

    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == FRONTEND
    assert "authorization" in response.headers["Access-Control-Allow-Headers"]


def test_preflight_from_unknown_origin_gets_no_cors_headers(api_client):
    response = preflight(api_client, "https://evil.example")

    assert "Access-Control-Allow-Origin" not in response.headers
