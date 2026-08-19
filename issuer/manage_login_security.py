"""Database-backed failed-login tracking for the management console."""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth.signals import user_login_failed
from django.utils import timezone

from axes.handlers.proxy import AxesProxyHandler
from axes.models import AccessAttempt

from config.ip_allowlist import get_axes_client_ip


def is_outside_manage_login(request, credentials=None) -> bool:
    return request.path != "/issuer/manage/login/"


def axes_lockout_response(request, original_response, credentials=None):
    """Keep the management login page and its lockout message."""
    return original_response


def get_failure_count(request) -> int:
    return AxesProxyHandler.get_failures(request)


def is_locked(request) -> tuple[bool, int]:
    locked = AxesProxyHandler.is_locked(request)
    if not locked:
        return False, 0

    latest_attempt = (
        AccessAttempt.objects.filter(ip_address=get_axes_client_ip(request))
        .order_by("-attempt_time")
        .first()
    )
    if latest_attempt is None:
        return True, settings.MANAGE_LOGIN_LOCKOUT_MINUTES * 60
    lock_until = latest_attempt.attempt_time + settings.AXES_COOLOFF_TIME
    seconds_left = max(0, int((lock_until - timezone.now()).total_seconds()))
    return True, seconds_left


def record_failed_login(request) -> int:
    user_login_failed.send(
        sender=__name__,
        credentials={"username": request.POST.get("username", "")},
        request=request,
    )
    return get_failure_count(request)


def clear_failed_logins(request) -> None:
    AxesProxyHandler.reset_attempts(ip_address=get_axes_client_ip(request))
