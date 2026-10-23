from datetime import date

import pytest
from django.utils import timezone

from apps.expenses.selectors import previous_month
from apps.expenses.tasks import send_monthly_summaries
from apps.expenses.tests.factories import ExpenseFactory
from config.celery import app

pytestmark = pytest.mark.django_db


def test_sends_summaries_for_the_given_month(mailoutbox):
    expense = ExpenseFactory(date=date(2026, 9, 15))
    ExpenseFactory(date=date(2026, 8, 15))

    sent = send_monthly_summaries(year=2026, month=9)

    assert sent == 1
    assert mailoutbox[0].to == [expense.user.email]


def test_defaults_to_the_previous_month(mailoutbox):
    today = timezone.localdate()
    expense = ExpenseFactory(date=previous_month(today))
    ExpenseFactory(date=today)

    sent = send_monthly_summaries()

    assert sent == 1
    assert mailoutbox[0].to == [expense.user.email]


def test_runs_through_celery(mailoutbox):
    ExpenseFactory(date=date(2026, 9, 15))

    result = send_monthly_summaries.apply(kwargs={"year": 2026, "month": 9})

    assert result.get() == 1


def test_monthly_summaries_are_scheduled_on_the_first_of_each_month():
    entry = app.conf.beat_schedule["send-monthly-summaries"]

    assert entry["task"] == send_monthly_summaries.name
    assert entry["schedule"].day_of_month == {1}
    assert entry["schedule"].hour == {7}
    assert entry["schedule"].minute == {0}


def test_recurring_expenses_are_created_every_day():
    entry = app.conf.beat_schedule["create-recurring-expenses"]

    assert entry["task"] == "apps.expenses.tasks.create_recurring_expenses"
    assert entry["schedule"].hour == {5}
    assert entry["schedule"].minute == {30}


def test_celery_uses_the_django_time_zone():
    assert app.conf.timezone == "UTC"
