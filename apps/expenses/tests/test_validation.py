"""Input that used to get through: dates that crash the month arithmetic and multi-line names."""

import csv
import io
from datetime import date

import pytest
from django.urls import reverse

from apps.expenses.tests.factories import CategoryFactory, ExpenseFactory

pytestmark = pytest.mark.django_db

EXPENSES_URL = reverse("expenses:expense-list")
CATEGORIES_URL = reverse("expenses:category-list")
RECURRING_URL = reverse("expenses:recurring-list")
SUMMARY_URL = reverse("expenses:expense-summary")
EXPORT_URL = reverse("expenses:expense-export")


@pytest.mark.parametrize("month", ["9999-12", "1899-12", "2101-01"])
def test_summary_rejects_months_out_of_range(auth_client, month):
    response = auth_client.get(SUMMARY_URL, {"month": month})

    assert response.status_code == 400
    assert "month" in response.data


@pytest.mark.parametrize("day", ["9999-12-31", "0001-01-01"])
def test_expense_dates_must_be_plausible(auth_client, day):
    response = auth_client.post(EXPENSES_URL, {"amount": "5", "date": day}, format="json")

    assert response.status_code == 400
    assert "date" in response.data


def test_category_names_are_a_single_line(auth_client):
    response = auth_client.post(CATEGORIES_URL, {"name": "Food\nBcc: x@example.com"})

    assert response.status_code == 400
    assert "name" in response.data


@pytest.mark.parametrize("url", [EXPENSES_URL, RECURRING_URL])
def test_descriptions_are_a_single_line(auth_client, url):
    data = {"amount": "5", "date": "2026-10-01", "day_of_month": 1, "description": "a\nb"}

    response = auth_client.post(url, data, format="json")

    assert response.status_code == 400
    assert "description" in response.data


def test_export_never_writes_a_formula(auth_client, user):
    category = CategoryFactory(user=user, name="@SUM(1+1)")
    ExpenseFactory(
        user=user,
        category=category,
        date=date(2026, 10, 1),
        description='=HYPERLINK("https://evil.example","Click")',
    )

    response = auth_client.get(EXPORT_URL, HTTP_ACCEPT_LANGUAGE="en")

    text = response.content.decode("utf-8").removeprefix("﻿")
    row = list(csv.reader(io.StringIO(text)))[1]
    assert row[1] == '\'=HYPERLINK("https://evil.example","Click")'
    assert row[2] == "'@SUM(1+1)"
