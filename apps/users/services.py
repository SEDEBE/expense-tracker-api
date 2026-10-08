from django.contrib.auth.password_validation import validate_password
from django.db import transaction

from .models import User


@transaction.atomic
def user_create(*, email: str, password: str, first_name: str = "", last_name: str = "") -> User:
    user = User(
        email=User.objects.normalize_email(email), first_name=first_name, last_name=last_name
    )
    validate_password(password, user=user)
    user.set_password(password)
    user.full_clean()
    user.save()
    return user
