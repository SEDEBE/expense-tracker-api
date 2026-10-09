from datetime import date

from django.contrib.auth import get_user_model
from django.core.mail import send_mail

from .selectors import month_range, monthly_summary


def monthly_summary_send(*, user, year: int, month: int) -> bool:
    """Email the user their summary for the month. Returns False if there was nothing to send."""
    summary = monthly_summary(user, year, month)
    if not summary["by_category"]:
        return False

    month_name = date(year, month, 1).strftime("%B %Y")
    lines = [
        "Hi,",
        "",
        f"Here is your expense summary for {month_name}.",
        "",
        f"Total: {summary['total']:.2f}",
        "",
        "By category:",
    ]
    for row in summary["by_category"]:
        name = row["category"] or "Uncategorized"
        expenses = "expense" if row["count"] == 1 else "expenses"
        lines.append(f"- {name}: {row['total']:.2f} ({row['count']} {expenses})")

    send_mail(
        subject=f"Your expense summary for {month_name}",
        message="\n".join(lines),
        from_email=None,
        recipient_list=[user.email],
    )
    return True


def monthly_summaries_send(*, year: int, month: int) -> int:
    """Email every active user who had expenses that month. Returns how many emails were sent."""
    start, end = month_range(year, month)
    users = (
        get_user_model()
        .objects.filter(is_active=True, expenses__date__gte=start, expenses__date__lt=end)
        .distinct()
    )
    return sum(monthly_summary_send(user=user, year=year, month=month) for user in users)
