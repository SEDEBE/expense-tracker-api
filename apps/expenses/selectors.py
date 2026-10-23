from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth


def month_range(year, month):
    """Return the first day of the month and the first day of the next one."""
    start = date(year, month, 1)
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return start, end


def previous_month(today: date) -> date:
    """First day of the month before `today`."""
    return (today.replace(day=1) - timedelta(days=1)).replace(day=1)


def add_months(day: date, months: int) -> date:
    """First day of the month `months` months after (or before, if negative) `day`'s month."""
    index = day.year * 12 + day.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


def monthly_summary(user, year, month):
    start, end = month_range(year, month)
    expenses = user.expenses.filter(date__gte=start, date__lt=end)

    total = expenses.aggregate(total=Sum("amount"))["total"] or Decimal("0")

    rows = (
        expenses.values("category_id", "category__name")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("-total", "category__name")
    )
    by_category = [
        {
            "category_id": row["category_id"],
            "category": row["category__name"],
            "total": row["total"],
            "count": row["count"],
        }
        for row in rows
    ]

    return {"total": total, "by_category": by_category}


def monthly_totals(user, *, last_month: date, months: int) -> list[dict]:
    """Total spent in each of the `months` months ending with `last_month`, oldest first.

    Months without expenses are included with a zero total, so charts get a continuous series.
    """
    first = add_months(last_month, -(months - 1))
    end = add_months(last_month, 1)
    rows = (
        user.expenses.filter(date__gte=first, date__lt=end)
        .annotate(month=TruncMonth("date"))
        .values("month")
        .annotate(total=Sum("amount"))
    )
    totals = {row["month"]: row["total"] for row in rows}
    series = (add_months(first, i) for i in range(months))
    return [{"month": month, "total": totals.get(month, Decimal("0"))} for month in series]
