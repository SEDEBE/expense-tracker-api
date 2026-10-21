from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.expenses.tests.factories import CategoryFactory, ExpenseFactory

pytestmark = pytest.mark.django_db


def test_name_is_unique_per_user_ignoring_case():
    category = CategoryFactory(name="Food")

    with pytest.raises(IntegrityError):
        CategoryFactory(user=category.user, name="FOOD")


def test_different_users_can_use_the_same_name():
    CategoryFactory(name="Food")
    CategoryFactory(name="Food")  # another user, created by the SubFactory


@pytest.mark.parametrize("amount", [Decimal("0"), Decimal("-5.00")])
def test_expense_amount_must_be_positive(amount):
    with pytest.raises(IntegrityError):
        ExpenseFactory(amount=amount)


def test_deleting_category_keeps_its_expenses():
    expense = ExpenseFactory()

    expense.category.delete()

    expense.refresh_from_db()
    assert expense.category is None


def test_expense_category_must_belong_to_the_same_user():
    expense = ExpenseFactory()
    expense.category = CategoryFactory()  # owned by another user

    with pytest.raises(ValidationError) as exc_info:
        expense.full_clean()

    assert "category" in exc_info.value.message_dict


def test_expense_with_own_category_or_no_category_is_valid():
    expense = ExpenseFactory()
    expense.full_clean()

    expense.category = None
    expense.full_clean()
