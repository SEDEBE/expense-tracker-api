from rest_framework import filters, viewsets

from .filters import ExpenseFilter
from .models import Category, Expense
from .serializers import CategorySerializer, ExpenseSerializer


class CategoryViewSet(viewsets.ModelViewSet):
    serializer_class = CategorySerializer

    def get_queryset(self):
        # drf-spectacular calls this without a real user to build the API docs.
        if getattr(self, "swagger_fake_view", False):
            return Category.objects.none()
        return self.request.user.categories.all()

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class ExpenseViewSet(viewsets.ModelViewSet):
    serializer_class = ExpenseSerializer
    filterset_class = ExpenseFilter
    filter_backends = [*viewsets.ModelViewSet.filter_backends, filters.OrderingFilter]
    ordering_fields = ["date", "amount", "created_at"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Expense.objects.none()
        return self.request.user.expenses.all()

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
