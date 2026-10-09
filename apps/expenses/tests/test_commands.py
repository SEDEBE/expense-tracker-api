from datetime import date
from io import StringIO

import pytest
from django.core.management import CommandError, call_command

from apps.expenses.management.commands.send_monthly_summaries import previous_month
from apps.expenses.tests.factories import ExpenseFactory

pytestmark = pytest.mark.django_db


def test_sends_summaries_for_the_given_month(mailoutbox):
    ExpenseFactory(date=date(2026, 9, 15))
    out = StringIO()

    call_command("send_monthly_summaries", "--month", "2026-09", stdout=out)

    assert len(mailoutbox) == 1
    assert "Sent 1 summaries for 2026-09." in out.getvalue()


def test_rejects_invalid_month():
    with pytest.raises(CommandError, match="YYYY-MM"):
        call_command("send_monthly_summaries", "--month", "september")


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
