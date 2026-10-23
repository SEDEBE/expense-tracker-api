from datetime import date

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import translation
from django.utils.formats import date_format, number_format
from django.utils.translation import gettext as _
from django.utils.translation import ngettext

from apps.core.emails import email_send

from .selectors import month_range, monthly_summary


def _money(value) -> str:
    """An amount in the active language: '€1,234.50' in English, '1.234,50 €' in Spanish."""
    return _("€%(amount)s") % {"amount": number_format(value, 2, force_grouping=True)}


def monthly_summary_send(*, user, year: int, month: int) -> bool:
    """Email the user their summary for the month. Returns False if there was nothing to send."""
    summary = monthly_summary(user, year, month)
    if not summary["by_category"]:
        return False

    # Texts, month names and number formats follow the user's language, not the active one.
    with translation.override(user.language):
        month_name = date_format(date(year, month, 1), "YEAR_MONTH_FORMAT")
        total = _money(summary["total"])
        lines = [
            _("Hi,"),
            "",
            _("Here is your expense summary for %(month)s.") % {"month": month_name},
            "",
            _("Total: %(total)s") % {"total": total},
            "",
            _("By category:"),
        ]
        rows = []
        biggest = max(row["total"] for row in summary["by_category"]) or 1
        for row in summary["by_category"]:
            name = row["category"] or _("Uncategorized")
            row_total = _money(row["total"])
            count = row["count"]
            expenses = ngettext("%(count)d expense", "%(count)d expenses", count) % {"count": count}
            lines.append(f"- {name}: {row_total} ({expenses})")
            # The bar never disappears completely, so even a tiny category is visible.
            width = max(2, round(row["total"] / biggest * 100))
            rows.append({"name": name, "total": row_total, "count": expenses, "width": width})
        subject = _("Your expense summary for %(month)s") % {"month": month_name}
        count = sum(row["count"] for row in summary["by_category"])
        app_url = settings.FRONTEND_URL.rstrip("/")

        email_send(
            to=user.email,
            subject=subject,
            text="\n".join(lines),
            template="emails/monthly_summary.html",
            context={
                "preheader": _("Total: %(total)s") % {"total": total},
                "month_name": month_name,
                "total": total,
                "count_line": ngettext("%(count)d expense", "%(count)d expenses", count)
                % {"count": count},
                "by_category_title": _("By category"),
                "rows": rows,
                "button_url": f"{app_url}/?mes={year}-{month:02d}",
                "button_label": _("Open it in the app"),
            },
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
