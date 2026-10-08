import pytest
from django.core.exceptions import ValidationError

from apps.users.services import user_create
from apps.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def test_user_create_hashes_password_and_normalizes_email():
    user = user_create(email="Ana@EXAMPLE.com", password="S3cure-pass!")

    assert user.email == "Ana@example.com"
    assert user.check_password("S3cure-pass!")
    assert user.password != "S3cure-pass!"


def test_user_create_rejects_weak_password():
    with pytest.raises(ValidationError):
        user_create(email="ana@example.com", password="123")


def test_user_create_rejects_duplicate_email():
    UserFactory(email="ana@example.com")

    with pytest.raises(ValidationError):
        user_create(email="ana@example.com", password="S3cure-pass!")
