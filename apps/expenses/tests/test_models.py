from decimal import Decimal

import pytest
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
