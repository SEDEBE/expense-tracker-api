from datetime import date
from decimal import Decimal

import pytest

from apps.expenses.selectors import add_months, monthly_summary, monthly_totals, previous_month
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


@pytest.mark.parametrize(
    ("today", "expected"),
    [
        (date(2026, 10, 1), date(2026, 9, 1)),
        (date(2026, 10, 31), date(2026, 9, 1)),
        (date(2026, 1, 15), date(2025, 12, 1)),
        (date(2024, 3, 31), date(2024, 2, 1)),
    ],
)
def test_previous_month(today, expected):
    assert previous_month(today) == expected


@pytest.mark.parametrize(
    ("day", "months", "expected"),
    [
        (date(2026, 10, 23), 0, date(2026, 10, 1)),
        (date(2026, 10, 23), 2, date(2026, 12, 1)),
        (date(2026, 11, 30), 3, date(2027, 2, 1)),
        (date(2026, 1, 31), -1, date(2025, 12, 1)),
        (date(2026, 3, 15), -14, date(2025, 1, 1)),
    ],
)
def test_add_months(day, months, expected):
    assert add_months(day, months) == expected


def test_monthly_totals_fills_months_without_expenses(user):
    ExpenseFactory(user=user, date=date(2026, 8, 3), amount=Decimal("10"))
    ExpenseFactory(user=user, date=date(2026, 8, 30), amount=Decimal("5.5"))
    ExpenseFactory(user=user, date=date(2026, 10, 1), amount=Decimal("7"))
    ExpenseFactory(user=user, date=date(2026, 7, 31), amount=Decimal("99"))  # before the range
    ExpenseFactory(date=date(2026, 9, 10), amount=Decimal("99"))  # another user

    totals = monthly_totals(user, last_month=date(2026, 10, 23), months=3)

    assert totals == [
        {"month": date(2026, 8, 1), "total": Decimal("15.50")},
        {"month": date(2026, 9, 1), "total": Decimal("0")},
        {"month": date(2026, 10, 1), "total": Decimal("7.00")},
    ]
