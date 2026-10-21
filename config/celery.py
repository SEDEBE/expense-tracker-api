"""Celery app. The worker and beat processes load it to find the settings and the tasks."""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("config")
# Read every Django setting that starts with CELERY_ (CELERY_BROKER_URL -> broker_url.)
app.config_from_object("django.conf:settings", namespace="CELERY")
# Find the tasks.py module of every installed app.
app.autodiscover_tasks()
