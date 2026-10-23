from urllib.parse import urlsplit

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.translation import get_language
from django.utils.translation import gettext as _


def email_send(*, to: str, subject: str, text: str, template: str, context: dict) -> None:
    """Send one email as plain text plus an HTML version rendered from `template`.

    Call it inside `translation.override(user.language)`: the shared footer is translated here.
    The plain text part stays because spam filters distrust HTML-only emails and some people
    read mail as text.
    """
    app_url = settings.FRONTEND_URL.rstrip("/")
    html = render_to_string(
        template,
        {
            "subject": subject,
            "language": get_language(),
            "app_url": app_url,
            "app_host": urlsplit(app_url).netloc,
            "footer": _("You get this email because you have an account on Gastos."),
            **context,
        },
    )
    send_mail(
        subject=subject, message=text, from_email=None, recipient_list=[to], html_message=html
    )
