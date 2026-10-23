from rest_framework.routers import DefaultRouter

from .views import CategoryViewSet, ExpenseViewSet, RecurringExpenseViewSet

app_name = "expenses"

router = DefaultRouter()
router.register("categories", CategoryViewSet, basename="category")
router.register("expenses", ExpenseViewSet, basename="expense")
router.register("recurring", RecurringExpenseViewSet, basename="recurring")

urlpatterns = router.urls
