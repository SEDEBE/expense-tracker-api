from decimal import Decimal

from rest_framework import serializers

from .models import Category, Expense


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_name(self, value):
        value = value.strip()
        user = self.context["request"].user
        duplicates = Category.objects.filter(user=user, name__iexact=value)
        if self.instance is not None:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError("You already have a category with this name.")
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
