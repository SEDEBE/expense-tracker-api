from datetime import date
from decimal import Decimal

import pytest

from apps.expenses.selectors import monthly_summary
from apps.expenses.tests.factories import CategoryFactory, ExpenseFactory

pytestmark = pytest.mark.django_db


def test_empty_month_returns_zero_total(user):
    summary = monthly_summary(user, 2026, 10)

    assert summary == {"total": Decimal("0"), "by_category": []}


def test_only_counts_expenses_in_that_month(user):
    ExpenseFactory(user=user, date=date(2026, 9, 30), amount=Decimal("1"))
    ExpenseFactory(user=user, date=date(2026, 10, 15), amount=Decimal("10"))
    ExpenseFactory(user=user, date=date(2026, 11, 1), amount=Decimal("100"))

    summary = monthly_summary(user, 2026, 10)

    assert summary["total"] == Decimal("10")


def test_only_counts_own_expenses(user):
    ExpenseFactory(user=user, date=date(2026, 10, 1), amount=Decimal("10"))
    ExpenseFactory(date=date(2026, 10, 1), amount=Decimal("999"))  # another user

    summary = monthly_summary(user, 2026, 10)

    assert summary["total"] == Decimal("10")


def test_groups_by_category_including_uncategorized(user):
    food = CategoryFactory(user=user, name="Food")
    ExpenseFactory(user=user, category=food, date=date(2026, 10, 1), amount=Decimal("20"))
    ExpenseFactory(user=user, category=food, date=date(2026, 10, 2), amount=Decimal("30"))
    ExpenseFactory(user=user, category=None, date=date(2026, 10, 3), amount=Decimal("5"))

    summary = monthly_summary(user, 2026, 10)

    assert summary["total"] == Decimal("55")
    assert summary["by_category"] == [
        {"category_id": food.pk, "category": "Food", "total": Decimal("50"), "count": 2},
        {"category_id": None, "category": None, "total": Decimal("5"), "count": 1},
    ]


def test_uses_a_fixed_number_of_queries(user, django_assert_num_queries):
    for _ in range(5):
        ExpenseFactory(user=user, date=date(2026, 10, 1))

    with django_assert_num_queries(2):
        monthly_summary(user, 2026, 10)
