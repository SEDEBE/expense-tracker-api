import pytest
from django.db import IntegrityError

from apps.expenses.tests.factories import CategoryFactory

pytestmark = pytest.mark.django_db


def test_name_is_unique_per_user_ignoring_case():
    category = CategoryFactory(name="Food")

    with pytest.raises(IntegrityError):
        CategoryFactory(user=category.user, name="FOOD")


def test_different_users_can_use_the_same_name():
    CategoryFactory(name="Food")
    CategoryFactory(name="Food")  # another user, created by the SubFactory
