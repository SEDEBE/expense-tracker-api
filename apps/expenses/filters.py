import django_filters

from .models import Category, Expense


def user_categories(request):
    # Same rule as the serializer: another user's category id is treated as nonexistent.
    if request is None:
        return Category.objects.none()
    return request.user.categories.all()


class ExpenseFilter(django_filters.FilterSet):
    date_from = django_filters.DateFilter(field_name="date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="date", lookup_expr="lte")
    amount_min = django_filters.NumberFilter(field_name="amount", lookup_expr="gte")
    amount_max = django_filters.NumberFilter(field_name="amount", lookup_expr="lte")
    category = django_filters.ModelChoiceFilter(queryset=user_categories)
    uncategorized = django_filters.BooleanFilter(field_name="category", lookup_expr="isnull")

    class Meta:
        model = Expense
        fields = []
