from django.conf import settings
from django.contrib import admin
from django.core.cache import cache
from django.http import HttpResponse
from django.utils.translation import gettext as _
from rest_framework.throttling import BaseThrottle


class LockoutAdminSite(admin.AdminSite):
    """The Django admin, locking an IP out after a few failed logins.

    The admin is a password form on the public internet, and bots try common passwords on
    every /admin/ they find. Only failures count, so the owner logging in is never slowed down.
    """

    def login(self, request, extra_context=None):
        # Same client IP as the API's throttling (it honours NUM_PROXIES behind Caddy).
        key = f"admin-login-failures:{BaseThrottle().get_ident(request)}"
        if request.method == "POST" and cache.get(key, 0) >= settings.ADMIN_LOGIN_MAX_FAILURES:
            return HttpResponse(_("Too many failed logins. Try again later."), status=429)

        response = super().login(request, extra_context)

        # A failed login shows the form again (200); a good one redirects.
        if request.method == "POST" and response.status_code == 200:
            cache.add(key, 0, timeout=settings.ADMIN_LOGIN_LOCKOUT_SECONDS)
            cache.incr(key)
        return response
