import argparse
from datetime import date, datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.expenses.selectors import previous_month
from apps.expenses.services import monthly_summaries_send


def parse_month(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m").date()
    except ValueError:
        raise argparse.ArgumentTypeError("use the YYYY-MM format, e.g. 2026-09") from None


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
