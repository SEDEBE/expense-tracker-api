import pytest
from django.urls import reverse

from apps.expenses.models import Category
from apps.expenses.tests.factories import CategoryFactory
from apps.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

LIST_URL = reverse("expenses:category-list")


def detail_url(pk):
    return reverse("expenses:category-detail", args=[pk])


class TestCategoryCrud:
    def test_create_assigns_current_user(self, auth_client, user):
        response = auth_client.post(LIST_URL, {"name": "Food"}, format="json")

        assert response.status_code == 201
        assert Category.objects.get(pk=response.data["id"]).user == user

    def test_create_ignores_user_sent_by_client(self, auth_client, user):
        other_user = UserFactory()

        response = auth_client.post(
            LIST_URL, {"name": "Food", "user": other_user.pk}, format="json"
        )

        assert response.status_code == 201
        assert Category.objects.get(pk=response.data["id"]).user == user

    def test_create_rejects_duplicate_name_ignoring_case_and_spaces(self, auth_client, user):
        CategoryFactory(user=user, name="Food")

        response = auth_client.post(LIST_URL, {"name": "  food "}, format="json")

        assert response.status_code == 400
        assert "name" in response.data

    def test_rename_only_changing_case_is_allowed(self, auth_client, user):
        category = CategoryFactory(user=user, name="Food")

        response = auth_client.patch(detail_url(category.pk), {"name": "food"}, format="json")

        assert response.status_code == 200
        category.refresh_from_db()
        assert category.name == "food"

    def test_list_is_sorted_by_name(self, auth_client, user):
        CategoryFactory(user=user, name="Transport")
        CategoryFactory(user=user, name="Food")

        response = auth_client.get(LIST_URL)

        assert [c["name"] for c in response.data["results"]] == ["Food", "Transport"]

    def test_delete(self, auth_client, user):
        category = CategoryFactory(user=user)

        response = auth_client.delete(detail_url(category.pk))

        assert response.status_code == 204
        assert not Category.objects.filter(pk=category.pk).exists()


class TestCategoryIsolation:
    def test_requires_authentication(self, api_client):
        assert api_client.get(LIST_URL).status_code == 401

    def test_list_only_shows_own_categories(self, auth_client, user):
        CategoryFactory(user=user, name="Mine")
        CategoryFactory(name="Someone else's")

        response = auth_client.get(LIST_URL)

        assert [c["name"] for c in response.data["results"]] == ["Mine"]

    @pytest.mark.parametrize("method", ["get", "patch", "delete"])
    def test_cannot_access_other_users_category(self, auth_client, method):
        others = CategoryFactory(name="Secret")

        response = getattr(auth_client, method)(detail_url(others.pk), {"name": "Hacked"})

        assert response.status_code == 404
        others.refresh_from_db()
        assert others.name == "Secret"