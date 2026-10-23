from celery import shared_task

from .services import demo_users_delete_expired


@shared_task
def delete_expired_demo_users() -> int:
    """Delete demo accounts older than DEMO_USER_TTL. Beat runs it every hour."""
    return demo_users_delete_expired()
