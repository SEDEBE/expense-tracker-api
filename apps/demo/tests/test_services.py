import random
from datetime import date, timedelta

import pytest
from django.utils import timezone

from apps.demo.data import CATEGORIES
from apps.demo.services import DEMO_MONTHS, demo_user_create, demo_users_delete_expired
from apps.expenses.models import Category, Expense
from apps.expenses.selectors import add_months
from apps.expenses.services import recurring_expenses_create
from apps.users.models import User
from apps.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

TODAY = date(2026, 10, 23)


def make_demo_user():
    return demo_user_create(today=TODAY, rng=random.Random(42))  # noqa: S311


def test_creates_a_spanish_demo_user_that_cannot_log_in_with_a_password():
    user = make_demo_user()

    assert user.is_demo
    assert user.language == "es"
    assert user.email.endswith("@demo.invalid")
    assert not user.has_usable_password()


def test_each_call_creates_a_different_user():
    assert make_demo_user().email != make_demo_user().email


def test_creates_the_sample_categories():
    user = make_demo_user()

    assert sorted(user.categories.values_list("name", flat=True)) == sorted(CATEGORIES)


def test_creates_expenses_in_every_demo_month_and_none_in_the_future():
    user = make_demo_user()
    expenses = user.expenses.all()

    months = {expense.date.replace(day=1) for expense in expenses}
    assert months == {add_months(TODAY, -offset) for offset in range(DEMO_MONTHS)}
    assert max(expense.date for expense in expenses) <= TODAY
    assert all(expense.amount > 0 for expense in expenses)
    assert all(expense.category.user_id == user.pk for expense in expenses)


def test_includes_the_monthly_rent():
    user = make_demo_user()

    rent = user.expenses.filter(description="Alquiler")
    assert rent.count() == DEMO_MONTHS
    assert {expense.date.day for expense in rent} == {1}


def test_has_budgets_and_up_to_date_recurring_expenses():
    user = make_demo_user()

    assert user.categories.filter(monthly_budget__isnull=False).exists()
    recurring = {item.description: item for item in user.recurring_expenses.all()}
    assert {"Alquiler", "Netflix", "Gimnasio"} <= set(recurring)
    assert "Luz" not in recurring  # its amount changes every month
    # Days already past this month are already in the sample data: next month is next.
    assert recurring["Alquiler"].next_date == date(2026, 11, 1)
    assert recurring["Alquiler"].last_date == date(2026, 10, 1)


def test_recurring_expenses_do_not_duplicate_the_sample_data():
    user = make_demo_user()
    before = user.expenses.count()

    recurring_expenses_create(today=TODAY)

    assert user.expenses.count() == before


class TestDeleteExpired:
    def test_deletes_old_demo_users_with_their_data(self):
        user = make_demo_user()

        deleted = demo_users_delete_expired(now=user.date_joined + timedelta(hours=25))

        assert deleted == 1
        assert not User.objects.filter(pk=user.pk).exists()
        assert not Category.objects.filter(user_id=user.pk).exists()
        assert not Expense.objects.filter(user_id=user.pk).exists()

    def test_keeps_recent_demo_users(self):
        user = make_demo_user()

        deleted = demo_users_delete_expired(now=user.date_joined + timedelta(hours=23))

        assert deleted == 0
        assert User.objects.filter(pk=user.pk).exists()

    def test_never_deletes_real_users(self):
        real_user = UserFactory(date_joined=timezone.now() - timedelta(days=365))

        assert demo_users_delete_expired() == 0
        assert User.objects.filter(pk=real_user.pk).exists()
