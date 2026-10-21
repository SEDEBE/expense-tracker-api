from celery import shared_task
from django.utils import timezone

from .selectors import previous_month
from .services import monthly_summaries_send


@shared_task
def send_monthly_summaries(year: int | None = None, month: int | None = None) -> int:
    """Email every user their summary of a month. Defaults to the previous one."""
    if year is None or month is None:
        last_month = previous_month(timezone.localdate())
        year, month = last_month.year, last_month.month
    return monthly_summaries_send(year=year, month=month)
