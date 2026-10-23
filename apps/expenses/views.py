from django.utils import timezone
from django.utils.formats import date_format
from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from .filters import ExpenseFilter
from .models import Category, Expense
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
from .tasks import send_monthly_summary_email


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
