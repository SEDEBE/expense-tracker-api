import unicodedata
from datetime import date
from decimal import Decimal

from django.utils.formats import date_format
from django.utils.translation import gettext as _
from rest_framework import serializers

from .models import Category, Expense, RecurringExpense

# Dates outside this range are typos, and past year 9999 the month arithmetic would crash.
MIN_DATE = date(1900, 1, 1)
MAX_DATE = date(2100, 12, 31)


def validate_date_range(value: date) -> date:
    if not MIN_DATE <= value <= MAX_DATE:
        raise serializers.ValidationError(
            _("Choose a date between %(min)s and %(max)s.")
            % {"min": date_format(MIN_DATE), "max": date_format(MAX_DATE)}
        )
    return value


def validate_single_line(value: str) -> str:
    """Names and descriptions are one line of text: no line breaks or other control characters.

    A line break in a category name would also break the subject of the budget alert email.
    """
    if any(unicodedata.category(char) == "Cc" for char in value):
        raise serializers.ValidationError(_("Use a single line without special characters."))
    return value


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "monthly_budget", "created_at"]
        read_only_fields = ["id", "created_at"]
        extra_kwargs = {"monthly_budget": {"min_value": Decimal("0.01")}}

    def validate_name(self, value):
        value = validate_single_line(value.strip())
        user = self.context["request"].user
        duplicates = Category.objects.filter(user=user, name__iexact=value)
        if self.instance is not None:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError(_("You already have a category with this name."))
        return value


class UserCategoryField(serializers.PrimaryKeyRelatedField):
    """Only accepts categories owned by the requesting user.

    Another user's category id gets the same "does not exist" error as a missing one,
    so the API never reveals which ids exist.
    """

    def get_queryset(self):
        return self.context["request"].user.categories.all()


class ExpenseSerializer(serializers.ModelSerializer):
    category = UserCategoryField(allow_null=True, required=False)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.01"))

    class Meta:
        model = Expense
        fields = ["id", "amount", "date", "description", "category", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_date(self, value):
        return validate_date_range(value)

    def validate_description(self, value):
        return validate_single_line(value)


class RecurringExpenseSerializer(serializers.ModelSerializer):
    category = UserCategoryField(allow_null=True, required=False)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.01"))
    day_of_month = serializers.IntegerField(min_value=1, max_value=31)

    class Meta:
        model = RecurringExpense
        fields = [
            "id",
            "amount",
            "description",
            "category",
            "day_of_month",
            "active",
            "next_date",
            "last_date",
            "created_at",
        ]
        read_only_fields = ["id", "next_date", "last_date", "created_at"]

    def validate_description(self, value):
        return validate_single_line(value.strip())


class MonthQuerySerializer(serializers.Serializer):
    month = serializers.DateField(
        input_formats=["%Y-%m"],
        required=False,
        help_text="Month in YYYY-MM format. Defaults to the current month.",
    )

    def validate_month(self, value):
        return validate_date_range(value)


class CategoryTotalSerializer(serializers.Serializer):
    category_id = serializers.IntegerField(allow_null=True)
    category = serializers.CharField(allow_null=True)
    total = serializers.DecimalField(max_digits=12, decimal_places=2)
    count = serializers.IntegerField()


class MonthlySummarySerializer(serializers.Serializer):
    month = serializers.CharField()
    total = serializers.DecimalField(max_digits=12, decimal_places=2)
    by_category = CategoryTotalSerializer(many=True)


class HistoryQuerySerializer(serializers.Serializer):
    months = serializers.IntegerField(
        min_value=1,
        max_value=24,
        default=6,
        help_text="How many months to return, ending with the current one.",
    )


class MonthTotalSerializer(serializers.Serializer):
    month = serializers.CharField()
    total = serializers.DecimalField(max_digits=12, decimal_places=2)


class DetailSerializer(serializers.Serializer):
    detail = serializers.CharField()
