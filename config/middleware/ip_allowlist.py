"""Block /admin/ and /issuer/manage/ for clients outside the configured IP allowlist."""

import logging

from django.conf import settings
from django.http import HttpResponseForbidden

from config.ip_allowlist import get_client_ip, ip_is_allowed, parse_ip_allowlist

logger = logging.getLogger(__name__)

RESTRICTED_PATH_PREFIXES = (
    "/admin/",
    "/issuer/manage/",
)


class RestrictedAdminIPMiddleware:
    """
    Enforce ADMIN_IP_ALLOWLIST on Django admin and the issuer management console.

    When DEBUG is True and the allowlist is empty, localhost is permitted for development.
    When DEBUG is False and the allowlist is empty, all restricted paths are denied.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._path_is_restricted(request.path) and not self._client_is_allowed(request):
            client_ip = get_client_ip(
                request,
                trust_x_forwarded_for=getattr(settings, "TRUST_X_FORWARDED_FOR", False),
            )
            allowlist = getattr(settings, "RESTRICTED_ADMIN_IP_ALLOWLIST", [])
            logger.warning(
                "Restricted admin/manage access denied for client IP %r (path=%s, "
                "TRUST_X_FORWARDED_FOR=%s, allowlist_entries=%d). "
                "In production behind nginx, allowlist your workstation IP (not the server IP) "
                "and set TRUST_X_FORWARDED_FOR=True.",
                client_ip,
                request.path,
                getattr(settings, "TRUST_X_FORWARDED_FOR", False),
                len(allowlist),
            )
            message = "Access to this area is not allowed from your network location."
            if settings.DEBUG:
                message += f" Detected client IP: {client_ip or '(unknown)'}."
            return HttpResponseForbidden(message)
        return self.get_response(request)

    @staticmethod
    def _path_is_restricted(path: str) -> bool:
        return any(path.startswith(prefix) for prefix in RESTRICTED_PATH_PREFIXES)

    def _client_is_allowed(self, request) -> bool:
        allowed = parse_ip_allowlist(getattr(settings, "RESTRICTED_ADMIN_IP_ALLOWLIST", []))
        if not allowed:
            return False
        client_ip = get_client_ip(
            request,
            trust_x_forwarded_for=getattr(settings, "TRUST_X_FORWARDED_FOR", False),
        )
        return ip_is_allowed(client_ip, allowed)
