from smtplib import SMTPException

from celery import shared_task
from django.contrib.auth import get_user_model
from django.utils import timezone

from .selectors import previous_month
from .services import monthly_summaries_send, monthly_summary_send


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
