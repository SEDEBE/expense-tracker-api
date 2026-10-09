from datetime import date
from decimal import Decimal

import pytest

from apps.expenses.services import monthly_summary_send
from apps.expenses.tests.factories import CategoryFactory, ExpenseFactory

pytestmark = pytest.mark.django_db


def test_sends_summary_email(user, mailoutbox):
    food = CategoryFactory(user=user, name="Food")
    ExpenseFactory(user=user, category=food, date=date(2026, 10, 1), amount=Decimal("12.25"))
    ExpenseFactory(user=user, category=food, date=date(2026, 10, 2), amount=Decimal("8.25"))
    ExpenseFactory(user=user, category=None, date=date(2026, 10, 3), amount=Decimal("4.5"))

    sent = monthly_summary_send(user=user, year=2026, month=10)

    assert sent is True
    assert len(mailoutbox) == 1
    email = mailoutbox[0]
    assert email.to == [user.email]
    assert email.subject == "Your expense summary for October 2026"
    assert "Total: 25.00" in email.body
    assert "- Food: 20.50 (2 expenses)" in email.body
    assert "- Uncategorized: 4.50 (1 expense)" in email.body


def test_sends_nothing_for_a_month_without_expenses(user, mailoutbox):
    ExpenseFactory(user=user, date=date(2026, 9, 30))

    sent = monthly_summary_send(user=user, year=2026, month=10)

    assert sent is False
    assert mailoutbox == []
