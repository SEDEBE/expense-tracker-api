from django.apps import AppConfig
from django.contrib.admin import apps as admin_apps


class CoreConfig(AppConfig):
    name = "apps.core"
    # This module has two configs; "apps.core" in INSTALLED_APPS means this one.
    default = True


class AdminConfig(admin_apps.AdminConfig):
    """Replaces django.contrib.admin in INSTALLED_APPS to use the site with login lockout."""

    default = False
    default_site = "apps.core.admin.LockoutAdminSite"
