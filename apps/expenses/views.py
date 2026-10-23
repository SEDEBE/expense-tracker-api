from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .filters import ExpenseFilter
from .models import Category, Expense
from .selectors import monthly_summary, monthly_totals
from .serializers import (
    CategorySerializer,
    ExpenseSerializer,
    HistoryQuerySerializer,
    MonthlySummarySerializer,
    MonthQuerySerializer,
    MonthTotalSerializer,
)


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

    @extend_schema(parameters=[MonthQuerySerializer], responses=MonthlySummarySerializer)
    @action(detail=False, methods=["get"], filter_backends=[], pagination_class=None)
    def summary(self, request):
        query = MonthQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        month = query.validated_data.get("month") or timezone.localdate()

        summary = monthly_summary(request.user, month.year, month.month)
        data = {"month": month.strftime("%Y-%m"), **summary}
        return Response(MonthlySummarySerializer(data).data)

    @extend_schema(parameters=[HistoryQuerySerializer], responses=MonthTotalSerializer(many=True))
    @action(detail=False, methods=["get"], filter_backends=[], pagination_class=None)
    def history(self, request):
        query = HistoryQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)

        rows = monthly_totals(
            request.user,
            last_month=timezone.localdate(),
            months=query.validated_data["months"],
        )
        data = [{"month": row["month"].strftime("%Y-%m"), "total": row["total"]} for row in rows]
        return Response(MonthTotalSerializer(data, many=True).data)
