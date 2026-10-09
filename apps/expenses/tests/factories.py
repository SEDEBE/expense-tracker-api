from decimal import Decimal

import factory

from apps.expenses.models import Category, Expense
from apps.users.tests.factories import UserFactory


class CategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Category

    user = factory.SubFactory(UserFactory)
    name = factory.Sequence(lambda n: f"Category {n}")


class ExpenseFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Expense

    user = factory.SubFactory(UserFactory)
    category = factory.SubFactory(CategoryFactory, user=factory.SelfAttribute("..user"))
    amount = Decimal("12.50")
    date = factory.Faker("date_this_year")
    description = factory.Faker("sentence", nb_words=3)
