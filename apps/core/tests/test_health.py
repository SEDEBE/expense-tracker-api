import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_health_reports_ok(api_client):
    response = api_client.get(reverse("health"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


@pytest.mark.django_db
def test_api_docs_are_public(api_client):
    assert api_client.get(reverse("schema")).status_code == 200
