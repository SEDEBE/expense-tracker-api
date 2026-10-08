import pytest

from apps.users.models import User

pytestmark = pytest.mark.django_db


def test_create_user_uses_email_as_identifier():
    user = User.objects.create_user(email="ana@EXAMPLE.com", password="S3cure-pass!")

    assert str(user) == "ana@example.com"
    assert not user.is_staff
    assert not user.is_superuser


def test_create_user_requires_email():
    with pytest.raises(ValueError, match="email"):
        User.objects.create_user(email="", password="S3cure-pass!")


def test_create_superuser_sets_flags():
    admin = User.objects.create_superuser(email="admin@example.com", password="S3cure-pass!")

    assert admin.is_staff
    assert admin.is_superuser


def test_create_superuser_rejects_non_staff():
    with pytest.raises(ValueError):
        User.objects.create_superuser(email="a@example.com", password="x", is_staff=False)
