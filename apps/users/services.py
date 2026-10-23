from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import translation
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.translation import gettext as _

from apps.core.emails import email_send

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


def password_reset_request(*, email: str) -> bool:
    """Email a reset link if an active, real account has this address. Returns whether it did.

    The API answers the same either way, so nobody can find out which emails have an account.
    Demo accounts have made-up addresses and are skipped.
    """
    from .tasks import send_password_reset_email  # avoid a circular import with tasks.py

    user = User.objects.filter(email__iexact=email.strip(), is_active=True, is_demo=False).first()
    if user is None:
        return False
    send_password_reset_email.delay(user.pk)
    return True


def password_reset_link(user: User) -> str:
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    return f"{settings.FRONTEND_URL.rstrip('/')}/restablecer?uid={uid}&token={token}"


def password_reset_email_send(*, user: User) -> None:
    hours = settings.PASSWORD_RESET_TIMEOUT // 3600
    link = password_reset_link(user)
    with translation.override(user.language):
        subject = _("Reset your password")
        expiry = _(
            "The link works for %(hours)d hours and only once. If you did not ask "
            "for it, ignore this email: your password stays the same."
        ) % {"hours": hours}
        text = "\n".join(
            [
                _("Hi,"),
                "",
                _(
                    "Someone asked to reset the password of your account. "
                    "If it was you, open this link to choose a new one:"
                ),
                "",
                link,
                "",
                expiry,
            ]
        )
        intro = _(
            "Someone asked to reset the password of your account. "
            "If it was you, choose a new one with the button below."
        )
        email_send(
            to=user.email,
            subject=subject,
            text=text,
            template="emails/password_reset.html",
            context={
                "preheader": intro,
                "intro": intro,
                "button_url": link,
                "button_label": _("Choose a new password"),
                "expiry": expiry,
                "fallback": _("If the button doesn't work, copy this link into your browser:"),
            },
        )


def password_reset_confirm(*, uid: str, token: str, password: str) -> User:
    """Set a new password from a reset link. Raises ValidationError for a bad link or password."""
    message = _("This link is not valid or has expired. Ask for a new one.")
    invalid = ValidationError({"detail": message})
    try:
        user = User.objects.get(pk=force_str(urlsafe_base64_decode(uid)), is_active=True)
    except ValueError, TypeError, OverflowError, User.DoesNotExist:
        raise invalid from None
    if not default_token_generator.check_token(user, token):
        raise invalid
    validate_password(password, user=user)
    user.set_password(password)
    user.save(update_fields=["password"])
    return user
