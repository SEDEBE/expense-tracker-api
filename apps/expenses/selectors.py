from datetime import date
from decimal import Decimal

from django.db.models import Count, Sum


def month_range(year, month):
    """Return the first day of the month and the first day of the next one."""
    start = date(year, month, 1)
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return start, end


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
