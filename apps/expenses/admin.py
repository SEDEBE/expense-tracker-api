from django.contrib import admin

from .models import Category, Expense


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "user", "created_at"]
    search_fields = ["name", "user__email"]
    list_select_related = ["user"]


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ["date", "amount", "description", "category", "user"]
    list_filter = ["date"]
    search_fields = ["description", "user__email"]
    list_select_related = ["category", "user"]
    date_hierarchy = "date"
