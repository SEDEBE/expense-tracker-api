import argparse
from datetime import date, datetime, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.expenses.services import monthly_summaries_send


def parse_month(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m").date()
    except ValueError:
        raise argparse.ArgumentTypeError("use the YYYY-MM format, e.g. 2026-09") from None


def previous_month(today: date) -> date:
    """First day of the month before `today`."""
    return (today.replace(day=1) - timedelta(days=1)).replace(day=1)


class Command(BaseCommand):
    help = "Email each user the expense summary of a month (by default, the previous one)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--month",
            type=parse_month,
            help="Month to summarize, in YYYY-MM format. Defaults to the previous month.",
        )

    def handle(self, *args, **options):
        month = options["month"] or previous_month(timezone.localdate())
        sent = monthly_summaries_send(year=month.year, month=month.month)
        self.stdout.write(self.style.SUCCESS(f"Sent {sent} summaries for {month:%Y-%m}."))
