from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.expenses.models import BudgetAlert
from apps.expenses.services import budget_alert_check
from apps.expenses.tests.factories import CategoryFactory, ExpenseFactory
from apps.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

TODAY = date(2026, 10, 20)


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch):
    monkeypatch.setattr("apps.expenses.services.timezone.localdate", lambda: TODAY)


@pytest.fixture
def food(user):
    return CategoryFactory(user=user, name="Food", monthly_budget=Decimal("100"))


class TestBudgetField:
    def test_sets_and_clears_a_category_budget(self, auth_client, food):
        url = reverse("expenses:category-detail", args=[food.pk])

        response = auth_client.patch(url, {"monthly_budget": "250.50"}, format="json")
        assert response.status_code == 200
        assert response.data["monthly_budget"] == "250.50"

        response = auth_client.patch(url, {"monthly_budget": None}, format="json")
        assert response.data["monthly_budget"] is None

    @pytest.mark.parametrize("value", ["0", "-5"])
    def test_rejects_a_budget_that_is_not_positive(self, auth_client, food, value):
        url = reverse("expenses:category-detail", args=[food.pk])

        response = auth_client.patch(url, {"monthly_budget": value}, format="json")

        assert response.status_code == 400
        assert "monthly_budget" in response.data


class TestBudgetAlerts:
    def test_emails_when_spending_reaches_80_percent(self, user, food, mailoutbox):
        ExpenseFactory(user=user, category=food, date=date(2026, 10, 2), amount=Decimal("50"))
        expense = ExpenseFactory(user=user, category=food, date=TODAY, amount=Decimal("35"))

        assert budget_alert_check(expense=expense) == 80
        assert len(mailoutbox) == 1
        email = mailoutbox[0]
        assert email.subject == "You've used 80% of your Food budget"
        assert "This month you've spent €85.00 of the €100.00 budget for Food." in email.body
        assert "You have €15.00 left." in email.body

    def test_emails_once_per_threshold_and_month(self, user, food, mailoutbox):
        first = ExpenseFactory(user=user, category=food, date=TODAY, amount=Decimal("85"))
        second = ExpenseFactory(user=user, category=food, date=TODAY, amount=Decimal("5"))

        budget_alert_check(expense=first)

        assert budget_alert_check(expense=second) is None
        assert len(mailoutbox) == 1

    def test_going_over_sends_the_100_percent_email_only(self, user, food, mailoutbox):
        expense = ExpenseFactory(user=user, category=food, date=TODAY, amount=Decimal("120"))

        assert budget_alert_check(expense=expense) == 100
        assert len(mailoutbox) == 1
        assert mailoutbox[0].subject == "You've gone over your Food budget"
        assert "You're €20.00 over budget." in mailoutbox[0].body
        # The 80% one is recorded too, so it never arrives after the 100% one.
        assert BudgetAlert.objects.filter(category=food).count() == 2

    def test_after_80_percent_going_over_still_warns(self, user, food, mailoutbox):
        budget_alert_check(
            expense=ExpenseFactory(user=user, category=food, date=TODAY, amount=Decimal("85"))
        )
        budget_alert_check(
            expense=ExpenseFactory(user=user, category=food, date=TODAY, amount=Decimal("20"))
        )

        assert [email.subject for email in mailoutbox] == [
            "You've used 80% of your Food budget",
            "You've gone over your Food budget",
        ]

    def test_is_written_in_the_users_language(self, food, mailoutbox):
        user = UserFactory(language="es")
        category = CategoryFactory(user=user, name="Comida", monthly_budget=Decimal("100"))
        expense = ExpenseFactory(user=user, category=category, date=TODAY, amount=Decimal("90"))

        budget_alert_check(expense=expense)

        assert mailoutbox[0].subject == "Llevas el 80 % del presupuesto de Comida"
        assert "Te quedan 10,00 €." in mailoutbox[0].body

    def test_ignores_spending_under_the_thresholds(self, user, food, mailoutbox):
        expense = ExpenseFactory(user=user, category=food, date=TODAY, amount=Decimal("79.99"))

        assert budget_alert_check(expense=expense) is None
        assert mailoutbox == []

    def test_ignores_expenses_of_other_months(self, user, food, mailoutbox):
        expense = ExpenseFactory(
            user=user, category=food, date=date(2026, 9, 30), amount=Decimal("500")
        )

        assert budget_alert_check(expense=expense) is None
        assert mailoutbox == []

    def test_ignores_categories_without_budget_and_uncategorized(self, user, mailoutbox):
        free = CategoryFactory(user=user, monthly_budget=None)

        assert (
            budget_alert_check(expense=ExpenseFactory(user=user, category=free, date=TODAY)) is None
        )
        assert (
            budget_alert_check(expense=ExpenseFactory(user=user, category=None, date=TODAY)) is None
        )
        assert mailoutbox == []

    def test_demo_accounts_get_no_alerts(self, mailoutbox):
        demo = UserFactory(is_demo=True)
        category = CategoryFactory(user=demo, monthly_budget=Decimal("10"))

        expense = ExpenseFactory(user=demo, category=category, date=TODAY, amount=Decimal("50"))

        assert budget_alert_check(expense=expense) is None
        assert mailoutbox == []

    def test_saving_an_expense_through_the_api_checks_the_budget(
        self, auth_client, food, mailoutbox, django_capture_on_commit_callbacks
    ):
        payload = {"amount": "90", "date": TODAY.isoformat(), "category": food.pk}

        with django_capture_on_commit_callbacks(execute=True):
            response = auth_client.post(reverse("expenses:expense-list"), payload, format="json")

        assert response.status_code == 201
        assert [email.subject for email in mailoutbox] == ["You've used 80% of your Food budget"]

    def test_editing_an_expense_through_the_api_checks_the_budget(
        self, auth_client, user, food, mailoutbox, django_capture_on_commit_callbacks
    ):
        expense = ExpenseFactory(user=user, category=food, date=TODAY, amount=Decimal("10"))
        url = reverse("expenses:expense-detail", args=[expense.pk])

        with django_capture_on_commit_callbacks(execute=True):
            auth_client.patch(url, {"amount": "150"}, format="json")

        assert [email.subject for email in mailoutbox] == ["You've gone over your Food budget"]
