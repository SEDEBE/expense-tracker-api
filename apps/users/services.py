from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.db import transaction

from .models import User


@transaction.atomic
def user_create(
    *,
    email: str,
    password: str,
    first_name: str = "",
    last_name: str = "",
    language: str = settings.LANGUAGE_CODE,
) -> User:
    user = User(
        email=User.objects.normalize_email(email),
        first_name=first_name,
        last_name=last_name,
        language=language,
    )
    validate_password(password, user=user)
    user.set_password(password)
    user.full_clean()
    user.save()
    return user


@transaction.atomic
def user_get_or_create_from_google(
    *,
    email: str,
    first_name: str = "",
    last_name: str = "",
    language: str = settings.LANGUAGE_CODE,
) -> User:
    """Return the user with this email, creating it if needed.

    Google has already verified the email, so an existing account with the same address is the
    same person. New users get no usable password: they log in with Google.
    """
    email = User.objects.normalize_email(email)
    user = User.objects.filter(email__iexact=email).first()
    if user is not None:
        return user
    user = User(email=email, first_name=first_name, last_name=last_name, language=language)
    user.set_unusable_password()
    user.full_clean()
    user.save()
    return user
