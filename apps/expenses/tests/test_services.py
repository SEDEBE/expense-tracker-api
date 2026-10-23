from datetime import date
from decimal import Decimal

import pytest

from apps.expenses.services import monthly_summaries_send, monthly_summary_send
from apps.expenses.tests.factories import CategoryFactory, ExpenseFactory
from apps.users.tests.factories import UserFactory

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
    assert "Total: €25.00" in email.body
    assert "- Food: €20.50 (2 expenses)" in email.body
    assert "- Uncategorized: €4.50 (1 expense)" in email.body


def test_sends_nothing_for_a_month_without_expenses(user, mailoutbox):
    ExpenseFactory(user=user, date=date(2026, 9, 30))

    sent = monthly_summary_send(user=user, year=2026, month=10)

    assert sent is False
    assert mailoutbox == []


def test_monthly_summaries_send_emails_only_users_with_expenses(mailoutbox):
    with_expenses = ExpenseFactory(date=date(2026, 10, 5)).user
    ExpenseFactory(user=with_expenses, date=date(2026, 10, 6))  # second expense, still one email
    ExpenseFactory(date=date(2026, 9, 30))  # another user, but not in October
    inactive = ExpenseFactory(date=date(2026, 10, 5)).user
    inactive.is_active = False
    inactive.save()

    sent = monthly_summaries_send(year=2026, month=10)

    assert sent == 1
    assert [email.to for email in mailoutbox] == [[with_expenses.email]]


def test_sends_summary_email_in_the_users_language(mailoutbox):
    user = UserFactory(language="es")
    food = CategoryFactory(user=user, name="Comida")
    ExpenseFactory(user=user, category=food, date=date(2026, 10, 1), amount=Decimal("12.25"))
    ExpenseFactory(user=user, category=food, date=date(2026, 10, 2), amount=Decimal("8.25"))
    ExpenseFactory(user=user, category=None, date=date(2026, 10, 3), amount=Decimal("4.5"))

    monthly_summary_send(user=user, year=2026, month=10)

    email = mailoutbox[0]
    assert email.subject == "Resumen de tus gastos de octubre de 2026"
    assert "Total: 25,00 €" in email.body
    assert "- Comida: 20,50 € (2 gastos)" in email.body
    assert "- Sin categoría: 4,50 € (1 gasto)" in email.body


def test_summary_email_has_an_html_version(mailoutbox, settings):
    settings.FRONTEND_URL = "https://gastos.example.com"
    user = UserFactory(language="es")
    food = CategoryFactory(user=user, name="Comida")
    ExpenseFactory(user=user, category=food, date=date(2026, 10, 1), amount=Decimal("30"))
    ExpenseFactory(user=user, category=None, date=date(2026, 10, 3), amount=Decimal("15"))

    monthly_summary_send(user=user, year=2026, month=10)

    html, mimetype = mailoutbox[0].alternatives[0]
    assert mimetype == "text/html"
    assert "45,00 €" in html
    assert "Comida" in html and "Sin categoría" in html
    # Each bar is the category's share of the biggest one.
    assert 'width="100%"' in html and 'width="50%"' in html
    assert "https://gastos.example.com/?mes=2026-10" in html
    assert "Recibes este email porque tienes una cuenta en Gastos." in html


def test_monthly_summaries_send_uses_each_users_language(mailoutbox):
    ExpenseFactory(user=UserFactory(email="ana@example.com", language="es"), date=date(2026, 10, 5))
    ExpenseFactory(user=UserFactory(email="bob@example.com", language="en"), date=date(2026, 10, 5))

    monthly_summaries_send(year=2026, month=10)

    subjects = {email.to[0]: email.subject for email in mailoutbox}
    assert subjects == {
        "ana@example.com": "Resumen de tus gastos de octubre de 2026",
        "bob@example.com": "Your expense summary for October 2026",
    }


def test_monthly_summaries_send_skips_demo_users(mailoutbox):
    ExpenseFactory(user=UserFactory(is_demo=True), date=date(2026, 10, 5))

    assert monthly_summaries_send(year=2026, month=10) == 0
    assert mailoutbox == []


def test_summary_amounts_group_thousands_with_a_dot_in_spanish(mailoutbox):
    user = UserFactory(language="es")
    ExpenseFactory(user=user, category=None, date=date(2026, 10, 1), amount=Decimal("1234.5"))

    monthly_summary_send(user=user, year=2026, month=10)

    assert "Total: 1.234,50 €" in mailoutbox[0].body
