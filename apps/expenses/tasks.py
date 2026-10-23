from smtplib import SMTPException

from celery import shared_task
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import Expense
from .selectors import previous_month
from .services import budget_alert_check, monthly_summaries_send, monthly_summary_send


@shared_task
def send_monthly_summaries(year: int | None = None, month: int | None = None) -> int:
    """Email every user their summary of a month. Defaults to the previous one."""
    if year is None or month is None:
        last_month = previous_month(timezone.localdate())
        year, month = last_month.year, last_month.month
    return monthly_summaries_send(year=year, month=month)


# One email to one person, so retrying it after a mail server error is safe.
@shared_task(autoretry_for=(SMTPException, ConnectionError), retry_backoff=True, max_retries=3)
def send_monthly_summary_email(user_id: int, year: int, month: int) -> bool:
    """Email one user their summary of a month, when they ask for it from the app."""
    user = get_user_model().objects.filter(pk=user_id, is_active=True).first()
    if user is None:
        return False
    return monthly_summary_send(user=user, year=year, month=month)


@shared_task(autoretry_for=(SMTPException, ConnectionError), retry_backoff=True, max_retries=3)
def check_budget_alert(expense_id: int) -> int | None:
    """Runs after an expense is saved, outside the request, so the API answers without waiting."""
    expense = Expense.objects.select_related("category", "user").filter(pk=expense_id).first()
    if expense is None:
        return None
    return budget_alert_check(expense=expense)
