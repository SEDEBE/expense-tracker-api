from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.expenses.models import Expense
from apps.expenses.tests.factories import CategoryFactory, ExpenseFactory

pytestmark = pytest.mark.django_db

LIST_URL = reverse("expenses:expense-list")


def detail_url(pk):
    return reverse("expenses:expense-detail", args=[pk])


def ids(response):
    return [e["id"] for e in response.data["results"]]


class TestExpenseCrud:
    def test_create_assigns_current_user(self, auth_client, user):
        category = CategoryFactory(user=user)
        payload = {
            "amount": "23.45",
            "date": "2026-10-01",
            "description": "Groceries",
            "category": category.pk,
        }

        response = auth_client.post(LIST_URL, payload, format="json")

        assert response.status_code == 201
        expense = Expense.objects.get(pk=response.data["id"])
        assert expense.user == user
        assert expense.amount == Decimal("23.45")
        assert expense.category == category

    def test_create_without_category(self, auth_client):
        response = auth_client.post(LIST_URL, {"amount": "5", "date": "2026-10-01"}, format="json")

        assert response.status_code == 201
        assert response.data["category"] is None

    @pytest.mark.parametrize("amount", ["0", "-1", "0.001", "abc"])
    def test_create_rejects_invalid_amount(self, auth_client, amount):
        response = auth_client.post(
            LIST_URL, {"amount": amount, "date": "2026-10-01"}, format="json"
        )

        assert response.status_code == 400
        assert "amount" in response.data

    def test_update(self, auth_client, user):
        expense = ExpenseFactory(user=user, amount=Decimal("10"))

        response = auth_client.patch(detail_url(expense.pk), {"amount": "12.30"}, format="json")

        assert response.status_code == 200
        expense.refresh_from_db()
        assert expense.amount == Decimal("12.30")

    def test_delete(self, auth_client, user):
        expense = ExpenseFactory(user=user)

        response = auth_client.delete(detail_url(expense.pk))

        assert response.status_code == 204
        assert not Expense.objects.filter(pk=expense.pk).exists()

    def test_list_is_newest_first(self, auth_client, user):
        old = ExpenseFactory(user=user, date=date(2026, 1, 1))
        new = ExpenseFactory(user=user, date=date(2026, 2, 1))

        response = auth_client.get(LIST_URL)

        assert ids(response) == [new.pk, old.pk]


class TestExpenseFilters:
    def test_filter_by_date_range(self, auth_client, user):
        ExpenseFactory(user=user, date=date(2026, 9, 30))
        inside = ExpenseFactory(user=user, date=date(2026, 10, 15))
        ExpenseFactory(user=user, date=date(2026, 11, 1))

        response = auth_client.get(LIST_URL, {"date_from": "2026-10-01", "date_to": "2026-10-31"})

        assert ids(response) == [inside.pk]

    def test_filter_by_amount_range(self, auth_client, user):
        ExpenseFactory(user=user, amount=Decimal("5"))
        inside = ExpenseFactory(user=user, amount=Decimal("50"))
        ExpenseFactory(user=user, amount=Decimal("500"))

        response = auth_client.get(LIST_URL, {"amount_min": "10", "amount_max": "100"})

        assert ids(response) == [inside.pk]

    def test_filter_by_category(self, auth_client, user):
        food = ExpenseFactory(user=user)
        ExpenseFactory(user=user)

        response = auth_client.get(LIST_URL, {"category": food.category.pk})

        assert ids(response) == [food.pk]

    def test_filter_uncategorized(self, auth_client, user):
        ExpenseFactory(user=user)
        loose = ExpenseFactory(user=user, category=None)

        response = auth_client.get(LIST_URL, {"uncategorized": "true"})

        assert ids(response) == [loose.pk]

    def test_order_by_amount(self, auth_client, user):
        big = ExpenseFactory(user=user, amount=Decimal("100"))
        small = ExpenseFactory(user=user, amount=Decimal("1"))

        response = auth_client.get(LIST_URL, {"ordering": "amount"})

        assert ids(response) == [small.pk, big.pk]


class TestExpenseIsolation:
    def test_requires_authentication(self, api_client):
        assert api_client.get(LIST_URL).status_code == 401

    def test_list_only_shows_own_expenses(self, auth_client, user):
        mine = ExpenseFactory(user=user)
        ExpenseFactory()

        response = auth_client.get(LIST_URL)

        assert ids(response) == [mine.pk]

    @pytest.mark.parametrize("method", ["get", "patch", "delete"])
    def test_cannot_access_other_users_expense(self, auth_client, method):
        others = ExpenseFactory(amount=Decimal("10"))

        response = getattr(auth_client, method)(detail_url(others.pk), {"amount": "1"})

        assert response.status_code == 404
        others.refresh_from_db()
        assert others.amount == Decimal("10")

    def test_cannot_use_other_users_category(self, auth_client):
        others_category = CategoryFactory()

        response = auth_client.post(
            LIST_URL,
            {"amount": "5", "date": "2026-10-01", "category": others_category.pk},
            format="json",
        )

        assert response.status_code == 400
        assert "category" in response.data
        assert not Expense.objects.exists()

    def test_filter_by_other_users_category_is_rejected(self, auth_client):
        others = ExpenseFactory()

        response = auth_client.get(LIST_URL, {"category": others.category.pk})

        assert response.status_code == 400


class TestExpenseSummary:
    url = reverse("expenses:expense-summary")

    def test_returns_month_totals(self, auth_client, user):
        food = CategoryFactory(user=user, name="Food")
        ExpenseFactory(user=user, category=food, date=date(2026, 10, 3), amount=Decimal("20.5"))
        ExpenseFactory(user=user, category=None, date=date(2026, 10, 9), amount=Decimal("4.5"))

        response = auth_client.get(self.url, {"month": "2026-10"})

        assert response.status_code == 200
        assert response.data == {
            "month": "2026-10",
            "total": "25.00",
            "by_category": [
                {"category_id": food.pk, "category": "Food", "total": "20.50", "count": 1},
                {"category_id": None, "category": None, "total": "4.50", "count": 1},
            ],
        }

    def test_defaults_to_current_month(self, auth_client, user):
        today = timezone.localdate()
        ExpenseFactory(user=user, date=today, amount=Decimal("7"))

        response = auth_client.get(self.url)

        assert response.status_code == 200
        assert response.data["month"] == today.strftime("%Y-%m")
        assert response.data["total"] == "7.00"

    @pytest.mark.parametrize("month", ["2026-13", "october", "2026-10-01"])
    def test_rejects_invalid_month(self, auth_client, month):
        response = auth_client.get(self.url, {"month": month})

        assert response.status_code == 400
        assert "month" in response.data

    def test_requires_authentication(self, api_client):
        assert api_client.get(self.url).status_code == 401
