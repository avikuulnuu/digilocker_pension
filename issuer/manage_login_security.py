"""Failed-login tracking and lockout for the management console."""

from __future__ import annotations

import time

from django.conf import settings
from django.core.cache import cache

from config.ip_allowlist import get_client_ip

FAILURE_CACHE_PREFIX = "manage_login:fail:"
LOCK_CACHE_PREFIX = "manage_login:lock:"


def _client_key(request) -> str:
    ip = get_client_ip(
        request,
        trust_x_forwarded_for=getattr(settings, "TRUST_X_FORWARDED_FOR", False),
    )
    return ip or "unknown"


def _failure_cache_key(request) -> str:
    return f"{FAILURE_CACHE_PREFIX}{_client_key(request)}"


def _lock_cache_key(request) -> str:
    return f"{LOCK_CACHE_PREFIX}{_client_key(request)}"


def get_failure_count(request) -> int:
    return int(cache.get(_failure_cache_key(request), 0))


def is_locked(request) -> tuple[bool, int]:
    """Return (locked, seconds_remaining). Works with LocMemCache (no cache.ttl)."""
    lock_until = cache.get(_lock_cache_key(request))
    if lock_until is None:
        return False, 0
    try:
        remaining = int(float(lock_until) - time.time())
    except (TypeError, ValueError):
        cache.delete(_lock_cache_key(request))
        return False, 0
    if remaining <= 0:
        cache.delete(_lock_cache_key(request))
        return False, 0
    return True, remaining


def record_failed_login(request) -> int:
    """Increment failure count; apply lockout when threshold reached. Returns new count."""
    fail_key = _failure_cache_key(request)
    lock_key = _lock_cache_key(request)
    lockout_seconds = settings.MANAGE_LOGIN_LOCKOUT_MINUTES * 60
    failure_ttl = lockout_seconds

    try:
        count = cache.incr(fail_key)
    except ValueError:
        cache.set(fail_key, 1, timeout=failure_ttl)
        count = 1

    max_failures = settings.MANAGE_LOGIN_MAX_FAILURES
    if count >= max_failures:
        cache.set(
            lock_key,
            time.time() + lockout_seconds,
            timeout=lockout_seconds,
        )
    return count


def clear_failed_logins(request) -> None:
    cache.delete(_failure_cache_key(request))
    cache.delete(_lock_cache_key(request))
