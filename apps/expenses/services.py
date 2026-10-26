import csv
import io
from datetime import date

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone, translation
from django.utils.formats import date_format, get_format, number_format
from django.utils.translation import gettext as _
from django.utils.translation import ngettext

from apps.core.emails import email_send

from .models import BudgetAlert, Expense, RecurringExpense
from .selectors import add_months, month_range, monthly_summary, occurrence


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


# A cell starting with one of these is a formula for Excel and LibreOffice: a description such as
# "=HYPERLINK(...)" would run when the file is opened ("CSV injection").
_FORMULA_STARTS = ("=", "+", "-", "@", "\t", "\r")


def _csv_text(value: str) -> str:
    """Text for a CSV cell that spreadsheets show as written and never run as a formula."""
    return f"'{value}" if value.startswith(_FORMULA_STARTS) else value


def expenses_csv(expenses) -> str:
    """The expenses as CSV in the active language, ready to open with a double click in Excel.

    Where the decimal separator is a comma (Spanish), Excel expects `;` between columns, so that
    is what it gets; English gets the standard `,` and a decimal point. A byte order mark at the
    start tells Excel the file is UTF-8, so accents survive.
    """
    decimal = get_format("DECIMAL_SEPARATOR")
    delimiter = ";" if decimal == "," else ","
    out = io.StringIO()
    out.write("\ufeff")
    writer = csv.writer(out, delimiter=delimiter, lineterminator="\r\n")
    writer.writerow([_("Date"), _("Description"), _("Category"), _("Amount")])
    for expense in expenses:
        writer.writerow(
            [
                expense.date.isoformat(),
                _csv_text(expense.description),
                _csv_text(expense.category.name) if expense.category else _("Uncategorized"),
                f"{expense.amount:.2f}".replace(".", decimal),
            ]
        )
    return out.getvalue()


# Percentages of a category's monthly budget that trigger an email, highest first.
BUDGET_THRESHOLDS = (100, 80)


def budget_alert_check(*, expense) -> int | None:
    """After an expense is saved, warn the user if its category just reached a budget threshold.

    Only this month counts, each threshold is emailed once per category and month, and when the
    spending jumps past several thresholds at once only the highest one is sent. Returns the
    threshold emailed, or None.
    """
    category, user = expense.category, expense.user
    today = timezone.localdate()
    if category is None or category.monthly_budget is None or user.is_demo:
        return None
    if (expense.date.year, expense.date.month) != (today.year, today.month):
        return None

    start, end = month_range(today.year, today.month)
    spent = user.expenses.filter(category=category, date__gte=start, date__lt=end).aggregate(
        total=Sum("amount")
    )["total"]
    percent = spent * 100 / category.monthly_budget
    reached = [threshold for threshold in BUDGET_THRESHOLDS if percent >= threshold]
    if not reached:
        return None

    # Recording every reached threshold means a lower one is never sent after a higher one.
    created = [
        BudgetAlert.objects.get_or_create(category=category, month=start, threshold=threshold)[1]
        for threshold in reached
    ]
    if not created[0]:
        return None
    _budget_alert_email_send(user=user, category=category, spent=spent, threshold=reached[0])
    return reached[0]


def _budget_alert_email_send(*, user, category, spent, threshold) -> None:
    budget = category.monthly_budget
    with translation.override(user.language):
        values = {"category": category.name, "spent": _money(spent), "budget": _money(budget)}
        if threshold >= 100:
            subject = _("You've gone over your %(category)s budget") % values
            status = _("You're %(amount)s over budget.") % {"amount": _money(spent - budget)}
        else:
            subject = _("You've used %(percent)d%% of your %(category)s budget") % {
                "percent": threshold,
                "category": category.name,
            }
            status = _("You have %(amount)s left.") % {"amount": _money(budget - spent)}
        progress = _("This month you've spent %(spent)s of the %(budget)s budget for %(category)s.")
        progress %= values
        app_url = settings.FRONTEND_URL.rstrip("/")
        email_send(
            to=user.email,
            subject=subject,
            text="\n".join([_("Hi,"), "", progress, status]),
            template="emails/budget_alert.html",
            context={
                "preheader": status,
                "progress": progress,
                "status": status,
                "over": threshold >= 100,
                "width": min(100, round(spent * 100 / budget)),
                "button_url": f"{app_url}/",
                "button_label": _("Open it in the app"),
            },
        )


def recurring_next_date(*, day_of_month: int, today: date, last_date: date | None = None) -> date:
    """The first day on or after today when a recurring expense should be created.

    If an expense was already created this month (`last_date`), the next one is next month's,
    so changing the day or resuming a paused one never charges the same month twice.
    """
    candidate = occurrence(today.year, today.month, day_of_month)
    already_this_month = last_date is not None and last_date >= today.replace(day=1)
    if candidate < today or already_this_month:
        following = add_months(today, 1)
        candidate = occurrence(following.year, following.month, day_of_month)
    return candidate


def recurring_expenses_create(*, today: date | None = None) -> list[Expense]:
    """Create the expenses of every active recurring expense that is due. Safe to run twice.

    A due date that was missed (the task did not run that day) is still created, with its own
    date, so nothing is lost.
    """
    from .tasks import check_budget_alert  # tasks.py imports this module

    today = today or timezone.localdate()
    created = []
    due = RecurringExpense.objects.filter(active=True, next_date__lte=today).select_related("user")
    for recurring in due:
        with transaction.atomic():
            recurring = RecurringExpense.objects.select_for_update().get(pk=recurring.pk)
            while recurring.active and recurring.next_date <= today:
                created.append(
                    Expense.objects.create(
                        user=recurring.user,
                        category=recurring.category,
                        amount=recurring.amount,
                        description=recurring.description,
                        date=recurring.next_date,
                    )
                )
                recurring.last_date = recurring.next_date
                following = add_months(recurring.next_date, 1)
                recurring.next_date = occurrence(
                    following.year, following.month, recurring.day_of_month
                )
            recurring.save(update_fields=["last_date", "next_date", "updated_at"])

    for expense in created:
        transaction.on_commit(lambda pk=expense.pk: check_budget_alert.delay(pk))
    return created
