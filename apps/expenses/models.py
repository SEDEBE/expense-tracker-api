from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.functions import Lower
from django.utils.translation import gettext as _


class Category(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="categories",
    )
    name = models.CharField(max_length=50)
    monthly_budget = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Spending limit per month; empty means no budget",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                "user",
                name="unique_category_name_per_user",
            ),
            models.CheckConstraint(
                condition=models.Q(monthly_budget__isnull=True) | models.Q(monthly_budget__gt=0),
                name="category_budget_positive",
            ),
        ]

    def __str__(self):
        return self.name


class Expense(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="expenses",
    )
    # Deleting a category keeps its expenses; they just become uncategorized.
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expenses",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField()
    description = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="expense_amount_positive",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "-date"], name="expense_user_date_idx"),
        ]

    def __str__(self):
        return f"{self.date} {self.amount} {self.description}".strip()

    def clean(self):
        super().clean()
        # The API already rejects other users' categories; this covers the admin and ModelForms.
        if self.category_id and self.user_id and self.category.user_id != self.user_id:
            raise ValidationError(
                {"category": _("The category must belong to the same user as the expense.")}
            )


class BudgetAlert(models.Model):
    """A budget warning already emailed, so each threshold is sent once per category and month."""

    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="budget_alerts")
    month = models.DateField(help_text="First day of the month the alert is about")
    threshold = models.PositiveSmallIntegerField(help_text="Percentage of the budget reached")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["category", "month", "threshold"], name="one_budget_alert_per_threshold"
            ),
        ]

    def __str__(self):
        return f"{self.category} {self.month:%Y-%m} {self.threshold}%"


class RecurringExpense(models.Model):
    """An expense that repeats every month on the same day, such as rent or a subscription.

    A daily task creates the real Expense on `next_date` and moves it to the next month.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recurring_expenses",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recurring_expenses",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=255)
    day_of_month = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(31)],
        help_text="In shorter months, days past the end fall on the last day",
    )
    active = models.BooleanField(default=True)
    next_date = models.DateField(help_text="Day the next expense will be created")
    last_date = models.DateField(null=True, blank=True, help_text="Day of the last expense created")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["day_of_month", "description"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="recurring_amount_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(day_of_month__gte=1, day_of_month__lte=31),
                name="recurring_day_of_month_valid",
            ),
        ]

    def __str__(self):
        return f"{self.description} ({self.amount}, day {self.day_of_month})"
