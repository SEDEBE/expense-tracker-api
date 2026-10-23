from datetime import date

from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.utils import translation
from django.utils.formats import date_format, number_format
from django.utils.translation import gettext as _
from django.utils.translation import ngettext

from .selectors import month_range, monthly_summary


def monthly_summary_send(*, user, year: int, month: int) -> bool:
    """Email the user their summary for the month. Returns False if there was nothing to send."""
    summary = monthly_summary(user, year, month)
    if not summary["by_category"]:
        return False

    # Texts, month names and number formats follow the user's language, not the active one.
    with translation.override(user.language):
        month_name = date_format(date(year, month, 1), "YEAR_MONTH_FORMAT")
        lines = [
            _("Hi,"),
            "",
            _("Here is your expense summary for %(month)s.") % {"month": month_name},
            "",
            _("Total: %(total)s") % {"total": number_format(summary["total"], 2)},
            "",
            _("By category:"),
        ]
        for row in summary["by_category"]:
            name = row["category"] or _("Uncategorized")
            total = number_format(row["total"], 2)
            count = row["count"]
            expenses = ngettext("%(count)d expense", "%(count)d expenses", count) % {"count": count}
            lines.append(f"- {name}: {total} ({expenses})")
        subject = _("Your expense summary for %(month)s") % {"month": month_name}

    send_mail(
        subject=subject,
        message="\n".join(lines),
        from_email=None,
        recipient_list=[user.email],
    )
    return True


def monthly_summaries_send(*, year: int, month: int) -> int:
    """Email every active user who had expenses that month. Returns how many emails were sent.

    Demo accounts are skipped: their addresses are fake and nobody reads them.
    """
    start, end = month_range(year, month)
    users = (
        get_user_model()
        .objects.filter(
            is_active=True,
            is_demo=False,
            expenses__date__gte=start,
            expenses__date__lt=end,
        )
        .distinct()
    )
    return sum(monthly_summary_send(user=user, year=year, month=month) for user in users)
