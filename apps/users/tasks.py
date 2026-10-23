from smtplib import SMTPException

from celery import shared_task

from .models import User
from .services import password_reset_email_send


# A reset email is one message, so retrying it after a mail server error is safe.
@shared_task(autoretry_for=(SMTPException, ConnectionError), retry_backoff=True, max_retries=3)
def send_password_reset_email(user_id: int) -> bool:
    user = User.objects.filter(pk=user_id, is_active=True).first()
    if user is None:
        return False
    password_reset_email_send(user=user)
    return True
