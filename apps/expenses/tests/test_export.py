import csv
import io
from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.expenses.tests.factories import CategoryFactory, ExpenseFactory
from apps.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

URL = reverse("expenses:expense-export")


def rows(response, delimiter):
    text = response.content.decode("utf-8")
    assert text.startswith("\ufeff"), "Excel needs the byte order mark to read UTF-8"
    return list(csv.reader(io.StringIO(text.removeprefix("\ufeff")), delimiter=delimiter))


def test_exports_the_users_expenses_as_csv(auth_client, user):
    food = CategoryFactory(user=user, name="Food")
    ExpenseFactory(
        user=user,
        category=food,
        date=date(2026, 10, 2),
        amount=Decimal("12.5"),
        description="Bread",
    )
    ExpenseFactory(
        user=user, category=None, date=date(2026, 10, 1), amount=Decimal("1234"), description="Rent"
    )
    ExpenseFactory(user=UserFactory(), date=date(2026, 10, 1), description="Not mine")

    response = auth_client.get(URL)

    assert response.status_code == 200
    assert response["Content-Type"] == "text/csv; charset=utf-8"
    assert response["Content-Disposition"].startswith('attachment; filename="expenses-')
    assert rows(response, ",") == [
        ["Date", "Description", "Category", "Amount"],
        ["2026-10-02", "Bread", "Food", "12.50"],
        ["2026-10-01", "Rent", "Uncategorized", "1234.00"],
    ]


def test_spanish_uses_semicolons_and_decimal_commas_for_excel(auth_client, user):
    ExpenseFactory(
        user=user, category=None, date=date(2026, 10, 1), amount=Decimal("8.25"), description="Pan"
    )

    response = auth_client.get(URL, HTTP_ACCEPT_LANGUAGE="es")

    assert response["Content-Disposition"].startswith('attachment; filename="gastos-')
    assert rows(response, ";") == [
        ["Fecha", "Descripción", "Categoría", "Importe"],
        ["2026-10-01", "Pan", "Sin categoría", "8,25"],
    ]


def test_uses_the_same_filters_and_ordering_as_the_list(auth_client, user):
    food = CategoryFactory(user=user, name="Food")
    ExpenseFactory(user=user, category=food, date=date(2026, 9, 30), amount=Decimal("1"))
    ExpenseFactory(user=user, category=food, date=date(2026, 10, 3), amount=Decimal("5"))
    ExpenseFactory(user=user, category=food, date=date(2026, 10, 4), amount=Decimal("9"))
    ExpenseFactory(user=user, category=None, date=date(2026, 10, 5), amount=Decimal("7"))

    response = auth_client.get(
        URL,
        {
            "date_from": "2026-10-01",
            "date_to": "2026-10-31",
            "category": food.pk,
            "ordering": "amount",
        },
    )

    assert [row[3] for row in rows(response, ",")[1:]] == ["5.00", "9.00"]


def test_works_when_the_client_asks_for_csv(auth_client):
    response = auth_client.get(URL, HTTP_ACCEPT="text/csv")

    assert response.status_code == 200


def test_requires_authentication(api_client):
    response = api_client.get(URL)

    assert response.status_code == 401
