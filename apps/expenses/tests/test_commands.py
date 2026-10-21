from datetime import date
from io import StringIO

import pytest
from django.core.management import CommandError, call_command

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
