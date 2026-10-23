import random
import uuid
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.expenses.models import Category, Expense
from apps.expenses.selectors import add_months, month_range
from apps.users.models import User

from .data import BUDGETS, CATEGORIES, MONTHLY, OCCASIONAL

# How many months of history a demo account starts with, the current one included.
DEMO_MONTHS = 6


@transaction.atomic
def demo_user_create(*, today: date | None = None, rng: random.Random | None = None) -> User:
    """Create a throwaway user with categories and a few months of realistic expenses.

    Each visitor gets their own account, so nobody sees what another visitor changed.
    The password is unusable: the only way in is the token returned by the demo endpoint.
    """
    today = today or timezone.localdate()
    rng = rng or random.Random()  # noqa: S311 - sample data, not security

    user = User(
        email=f"demo-{uuid.uuid4().hex[:12]}@demo.invalid",
        first_name="Demo",
        language="es",
        is_demo=True,
    )
    user.set_unusable_password()
    user.save()

    categories = {
        name: Category(user=user, name=name, monthly_budget=BUDGETS.get(name))
        for name in CATEGORIES
    }
    Category.objects.bulk_create(categories.values())
    Expense.objects.bulk_create(_sample_expenses(user, categories, today, rng))
    return user


def _sample_expenses(user, categories, today, rng):
    expenses = []
    for offset in range(-(DEMO_MONTHS - 1), 1):
        month = add_months(today, offset)
        start, end = month_range(month.year, month.month)
        # The current month only has expenses up to today, like a real account would.
        last_day = today.day if offset == 0 else (end - start).days
        share_of_month = last_day / (end - start).days

        for category, description, day, low, high in MONTHLY:
            if day <= last_day:
                expenses.append(
                    Expense(
                        user=user,
                        category=categories[category],
                        description=description,
                        date=start.replace(day=day),
                        amount=_amount(rng, low, high),
                    )
                )

        for category, descriptions, min_times, max_times, low, high in OCCASIONAL:
            times = round(rng.randint(min_times, max_times) * share_of_month)
            for _ in range(times):
                expenses.append(
                    Expense(
                        user=user,
                        category=categories[category],
                        description=rng.choice(descriptions),
                        date=start.replace(day=rng.randint(1, last_day)),
                        amount=_amount(rng, low, high),
                    )
                )
    return expenses


def _amount(rng: random.Random, low: Decimal, high: Decimal) -> Decimal:
    cents = rng.randint(int(low * 100), int(high * 100))
    return Decimal(cents) / 100


def demo_users_delete_expired(*, now=None) -> int:
    """Delete demo users older than DEMO_USER_TTL, with all their data. Returns how many."""
    now = now or timezone.now()
    cutoff = now - settings.DEMO_USER_TTL
    _, deleted = User.objects.filter(is_demo=True, date_joined__lt=cutoff).delete()
    return deleted.get(User._meta.label, 0)
