from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.translation import gettext as _
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from .filters import ExpenseFilter
from .models import Category, Expense
from .renderers import CSVRenderer
from .selectors import monthly_summary, monthly_totals
from .serializers import (
    CategorySerializer,
    DetailSerializer,
    ExpenseSerializer,
    HistoryQuerySerializer,
    MonthlySummarySerializer,
    MonthQuerySerializer,
    MonthTotalSerializer,
)
from .services import expenses_csv
from .tasks import check_budget_alert, send_monthly_summary_email


class SummaryEmailThrottle(UserRateThrottle):
    """Each request sends a real email: a few per hour is plenty and stops inbox flooding."""

    scope = "summary_email"


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
        expense = serializer.save(user=self.request.user)
        self._check_budget(expense)

    def perform_update(self, serializer):
        self._check_budget(serializer.save())

    @staticmethod
    def _check_budget(expense):
        # After the commit, so the worker sees the saved expense.
        transaction.on_commit(lambda: check_budget_alert.delay(expense.pk))

    @extend_schema(responses={(200, "text/csv"): OpenApiTypes.STR})
    @action(
        detail=False,
        methods=["get"],
        pagination_class=None,
        renderer_classes=[JSONRenderer, CSVRenderer],
    )
    def export(self, request):
        """Download the expenses as CSV, with the same filters and ordering as the list."""
        expenses = self.filter_queryset(self.get_queryset()).select_related("category")
        filename = f"{_('expenses')}-{timezone.localdate().isoformat()}.csv"
        return HttpResponse(
            expenses_csv(expenses),
            content_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @extend_schema(parameters=[MonthQuerySerializer], responses=MonthlySummarySerializer)
    @action(detail=False, methods=["get"], filter_backends=[], pagination_class=None)
    def summary(self, request):
        query = MonthQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        month = query.validated_data.get("month") or timezone.localdate()

        summary = monthly_summary(request.user, month.year, month.month)
        data = {"month": month.strftime("%Y-%m"), **summary}
        return Response(MonthlySummarySerializer(data).data)

    @extend_schema(
        request=MonthQuerySerializer,
        responses={
            202: OpenApiResponse(DetailSerializer, description="The email is on its way."),
            400: OpenApiResponse(DetailSerializer, description="No expenses that month."),
            403: OpenApiResponse(DetailSerializer, description="Demo accounts get no emails."),
        },
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="summary/email",
        filter_backends=[],
        pagination_class=None,
        throttle_classes=[UserRateThrottle, SummaryEmailThrottle],
    )
    def summary_email(self, request):
        """Email the user their summary of a month (the current one by default), right now."""
        query = MonthQuerySerializer(data=request.data)
        query.is_valid(raise_exception=True)
        month = query.validated_data.get("month") or timezone.localdate()

        if request.user.is_demo:
            raise PermissionDenied(
                _("Demo accounts have a made-up email address, so they can't receive emails.")
            )
        if not monthly_summary(request.user, month.year, month.month)["by_category"]:
            month_name = date_format(month, "YEAR_MONTH_FORMAT")
            message = _("There are no expenses in %(month)s to send.") % {"month": month_name}
            return Response(
                {"detail": message},
                status=status.HTTP_400_BAD_REQUEST,
            )

        send_monthly_summary_email.delay(request.user.pk, month.year, month.month)
        message = _("We're sending the summary to %(email)s.") % {"email": request.user.email}
        return Response(
            {"detail": message},
            status=status.HTTP_202_ACCEPTED,
        )

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
