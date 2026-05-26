"""Block /admin/ and /issuer/manage/ for clients outside the configured IP allowlist."""

from django.conf import settings
from django.http import HttpResponseForbidden

from config.ip_allowlist import get_client_ip, ip_is_allowed, parse_ip_allowlist

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
        self._allowed = parse_ip_allowlist(getattr(settings, "RESTRICTED_ADMIN_IP_ALLOWLIST", []))

    def __call__(self, request):
        if self._path_is_restricted(request.path) and not self._client_is_allowed(request):
            return HttpResponseForbidden(
                "Access to this area is not allowed from your network location."
            )
        return self.get_response(request)

    @staticmethod
    def _path_is_restricted(path: str) -> bool:
        return any(path.startswith(prefix) for prefix in RESTRICTED_PATH_PREFIXES)

    def _client_is_allowed(self, request) -> bool:
        if not self._allowed:
            return False
        client_ip = get_client_ip(
            request,
            trust_x_forwarded_for=getattr(settings, "TRUST_X_FORWARDED_FOR", False),
        )
        return ip_is_allowed(client_ip, self._allowed)
