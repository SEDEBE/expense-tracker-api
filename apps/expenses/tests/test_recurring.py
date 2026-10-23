from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.expenses.models import Expense, RecurringExpense
from apps.expenses.selectors import occurrence
from apps.expenses.services import recurring_expenses_create, recurring_next_date
from apps.expenses.tests.factories import CategoryFactory
from apps.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

LIST_URL = reverse("expenses:recurring-list")


def detail_url(pk):
    return reverse("expenses:recurring-detail", args=[pk])


def make_recurring(user, *, day=5, next_date, **fields):
    return RecurringExpense.objects.create(
        user=user,
        amount=fields.pop("amount", Decimal("650")),
        description=fields.pop("description", "Rent"),
        day_of_month=day,
        next_date=next_date,
        **fields,
    )


class TestDates:
    def test_short_months_use_their_last_day(self):
        assert occurrence(2026, 2, 31) == date(2026, 2, 28)
        assert occurrence(2028, 2, 30) == date(2028, 2, 29)
        assert occurrence(2026, 11, 31) == date(2026, 11, 30)
        assert occurrence(2026, 10, 31) == date(2026, 10, 31)

    def test_next_date_is_this_month_if_the_day_has_not_passed(self):
        assert recurring_next_date(day_of_month=25, today=date(2026, 10, 20)) == date(2026, 10, 25)
        assert recurring_next_date(day_of_month=20, today=date(2026, 10, 20)) == date(2026, 10, 20)

    def test_next_date_is_next_month_if_the_day_has_passed(self):
        assert recurring_next_date(day_of_month=5, today=date(2026, 10, 20)) == date(2026, 11, 5)
        assert recurring_next_date(day_of_month=31, today=date(2026, 12, 31)) == date(2026, 12, 31)
        assert recurring_next_date(day_of_month=5, today=date(2026, 12, 20)) == date(2027, 1, 5)

    def test_never_charges_a_month_that_already_had_its_expense(self):
        # Created on the 5th; moving it to the 25th on the 20th waits until next month.
        next_date = recurring_next_date(
            day_of_month=25, today=date(2026, 10, 20), last_date=date(2026, 10, 5)
        )
        assert next_date == date(2026, 11, 25)


class TestCreation:
    def test_creates_the_expense_on_its_day_and_moves_to_next_month(self, user):
        food = CategoryFactory(user=user)
        recurring = make_recurring(user, day=5, next_date=date(2026, 10, 5), category=food)

        created = recurring_expenses_create(today=date(2026, 10, 5))

        assert len(created) == 1
        expense = created[0]
        assert (expense.user, expense.category, expense.date) == (user, food, date(2026, 10, 5))
        assert (expense.amount, expense.description) == (Decimal("650"), "Rent")
        recurring.refresh_from_db()
        assert recurring.last_date == date(2026, 10, 5)
        assert recurring.next_date == date(2026, 11, 5)

    def test_does_nothing_before_the_day(self, user):
        make_recurring(user, next_date=date(2026, 10, 5))

        assert recurring_expenses_create(today=date(2026, 10, 4)) == []

    def test_running_twice_creates_it_once(self, user):
        make_recurring(user, next_date=date(2026, 10, 5))

        recurring_expenses_create(today=date(2026, 10, 5))
        recurring_expenses_create(today=date(2026, 10, 5))

        assert Expense.objects.count() == 1

    def test_catches_up_on_missed_months_with_their_own_dates(self, user):
        make_recurring(user, day=31, next_date=date(2026, 8, 31))

        created = recurring_expenses_create(today=date(2026, 10, 2))

        assert [expense.date for expense in created] == [date(2026, 8, 31), date(2026, 9, 30)]

    def test_paused_ones_are_skipped(self, user):
        make_recurring(user, next_date=date(2026, 10, 5), active=False)

        assert recurring_expenses_create(today=date(2026, 10, 5)) == []

    def test_new_expenses_go_through_the_budget_check(
        self, user, mailoutbox, monkeypatch, django_capture_on_commit_callbacks
    ):
        monkeypatch.setattr("apps.expenses.services.timezone.localdate", lambda: date(2026, 10, 5))
        rent = CategoryFactory(user=user, name="Home", monthly_budget=Decimal("600"))
        make_recurring(user, next_date=date(2026, 10, 5), category=rent)

        with django_capture_on_commit_callbacks(execute=True):
            recurring_expenses_create()

        assert [email.subject for email in mailoutbox] == ["You've gone over your Home budget"]


class TestApi:
    @pytest.fixture(autouse=True)
    def fixed_today(self, monkeypatch):
        monkeypatch.setattr("apps.expenses.views.timezone.localdate", lambda: date(2026, 10, 20))

    def test_creates_one_with_its_next_date(self, auth_client, user):
        category = CategoryFactory(user=user)
        payload = {
            "amount": "13.99",
            "description": " Netflix ",
            "category": category.pk,
            "day_of_month": 12,
        }

        response = auth_client.post(LIST_URL, payload, format="json")

        assert response.status_code == 201
        assert response.data["description"] == "Netflix"
        assert response.data["next_date"] == "2026-11-12"
        assert response.data["active"] is True
        assert RecurringExpense.objects.get().user == user

    def test_lists_only_the_users_own(self, auth_client, user):
        make_recurring(user, description="Mine", next_date=date(2026, 11, 5))
        make_recurring(UserFactory(), description="Theirs", next_date=date(2026, 11, 5))

        response = auth_client.get(LIST_URL)

        assert [row["description"] for row in response.data["results"]] == ["Mine"]

    def test_rejects_another_users_category(self, auth_client):
        other = CategoryFactory(user=UserFactory())
        payload = {"amount": "10", "description": "Gym", "category": other.pk, "day_of_month": 2}

        response = auth_client.post(LIST_URL, payload, format="json")

        assert response.status_code == 400
        assert "category" in response.data

    @pytest.mark.parametrize("day", [0, 32])
    def test_rejects_a_day_outside_the_month(self, auth_client, day):
        payload = {"amount": "10", "description": "Gym", "day_of_month": day}

        response = auth_client.post(LIST_URL, payload, format="json")

        assert response.status_code == 400
        assert "day_of_month" in response.data

    def test_changing_the_day_moves_the_next_date(self, auth_client, user):
        recurring = make_recurring(
            user, day=5, next_date=date(2026, 11, 5), last_date=date(2026, 10, 5)
        )

        response = auth_client.patch(detail_url(recurring.pk), {"day_of_month": 25}, format="json")

        assert response.data["next_date"] == "2026-11-25"

    def test_changing_the_amount_keeps_the_next_date(self, auth_client, user):
        recurring = make_recurring(user, day=25, next_date=date(2026, 10, 25))

        response = auth_client.patch(detail_url(recurring.pk), {"amount": "700"}, format="json")

        assert response.data["next_date"] == "2026-10-25"
        assert response.data["amount"] == "700.00"

    def test_resuming_a_paused_one_skips_the_missed_dates(self, auth_client, user):
        recurring = make_recurring(user, day=5, next_date=date(2026, 8, 5), active=False)

        response = auth_client.patch(detail_url(recurring.pk), {"active": True}, format="json")

        assert response.data["next_date"] == "2026-11-05"

    def test_cannot_touch_another_users(self, auth_client):
        theirs = make_recurring(UserFactory(), next_date=date(2026, 11, 5))

        response = auth_client.delete(detail_url(theirs.pk))

        assert response.status_code == 404
