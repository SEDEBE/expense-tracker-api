from datetime import timedelta

import pytest
from django.utils import timezone

from apps.demo.tasks import delete_expired_demo_users
from apps.users.models import User
from apps.users.tests.factories import UserFactory
from config.celery import app

pytestmark = pytest.mark.django_db


def test_deletes_expired_demo_users_through_celery():
    UserFactory(is_demo=True, date_joined=timezone.now() - timedelta(days=2))
    recent = UserFactory(is_demo=True)

    result = delete_expired_demo_users.apply()

    assert result.get() == 1
    assert list(User.objects.filter(is_demo=True)) == [recent]


def test_is_scheduled_every_hour():
    entry = app.conf.beat_schedule["delete-expired-demo-users"]

    assert entry["task"] == delete_expired_demo_users.name
    assert entry["schedule"].minute == {15}
    assert len(entry["schedule"].hour) == 24
