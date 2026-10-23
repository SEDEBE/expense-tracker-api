from datetime import date
from decimal import Decimal

import pytest
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone

from apps.expenses.tests.factories import CategoryFactory, ExpenseFactory
from apps.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

URL = reverse("expenses:expense-summary-email")


@pytest.fixture(autouse=True)
def clear_throttle_history():
    # Throttling counts requests in the cache, which would otherwise carry over between tests.
    cache.clear()
    yield
    cache.clear()


def test_emails_the_summary_of_the_chosen_month(auth_client, user, mailoutbox):
    food = CategoryFactory(user=user, name="Food")
    ExpenseFactory(user=user, category=food, date=date(2026, 9, 3), amount=Decimal("12.50"))

    response = auth_client.post(URL, {"month": "2026-09"}, format="json")

    assert response.status_code == 202
    assert response.data["detail"] == f"We're sending the summary to {user.email}."
    assert len(mailoutbox) == 1
    assert mailoutbox[0].to == [user.email]
    assert mailoutbox[0].subject == "Your expense summary for September 2026"
    assert "- Food: €12.50 (1 expense)" in mailoutbox[0].body


def test_defaults_to_the_current_month(auth_client, user, mailoutbox):
    ExpenseFactory(user=user, date=timezone.localdate(), amount=Decimal("5"))

    response = auth_client.post(URL, {}, format="json")

    assert response.status_code == 202
    assert len(mailoutbox) == 1


def test_a_month_without_expenses_sends_nothing(auth_client, user, mailoutbox):
    ExpenseFactory(user=user, date=date(2026, 9, 3))

    response = auth_client.post(URL, {"month": "2026-08"}, format="json")

    assert response.status_code == 400
    assert response.data["detail"] == "There are no expenses in August 2026 to send."
    assert mailoutbox == []


def test_answers_in_the_requested_language(auth_client, user):
    response = auth_client.post(URL, {"month": "2026-08"}, format="json", HTTP_ACCEPT_LANGUAGE="es")

    assert response.data["detail"] == "No hay gastos en agosto de 2026 que enviar."


def test_only_counts_the_users_own_expenses(auth_client, mailoutbox):
    ExpenseFactory(user=UserFactory(), date=date(2026, 9, 3))

    response = auth_client.post(URL, {"month": "2026-09"}, format="json")

    assert response.status_code == 400
    assert mailoutbox == []


def test_demo_accounts_cannot_receive_emails(api_client, mailoutbox):
    demo = UserFactory(is_demo=True)
    ExpenseFactory(user=demo, date=date(2026, 9, 3))
    api_client.force_authenticate(user=demo)

    response = api_client.post(URL, {"month": "2026-09"}, format="json")

    assert response.status_code == 403
    assert mailoutbox == []


def test_rejects_a_badly_written_month(auth_client):
    response = auth_client.post(URL, {"month": "09/2026"}, format="json")

    assert response.status_code == 400
    assert "month" in response.data


def test_requires_authentication(api_client):
    response = api_client.post(URL, {}, format="json")

    assert response.status_code == 401


def test_is_limited_to_a_few_emails_per_hour(auth_client, user, mailoutbox):
    ExpenseFactory(user=user, date=date(2026, 9, 3))

    responses = [auth_client.post(URL, {"month": "2026-09"}, format="json") for _ in range(6)]
    statuses = [response.status_code for response in responses]

    assert statuses == [202] * 5 + [429]
    assert len(mailoutbox) == 5
