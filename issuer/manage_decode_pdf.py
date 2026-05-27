"""Feature flag and guards for the manage-portal Base64 PDF decoder."""

from __future__ import annotations

import re
from functools import wraps

from django.conf import settings
from django.http import Http404

_TOKEN_PATTERN = re.compile(r"^[-\w]{16,64}$")


def manage_decode_pdf_enabled() -> bool:
    return bool(getattr(settings, "MANAGE_DECODE_PDF_ENABLED", False))


def require_decode_pdf_enabled(view_func):
    """Return 404 when the decoder tool is disabled (routes may still be registered)."""

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not manage_decode_pdf_enabled():
            raise Http404()
        return view_func(request, *args, **kwargs)

    return wrapper


def validate_decode_pdf_token(token: str) -> None:
    if not token or not _TOKEN_PATTERN.fullmatch(token):
        raise Http404("Decoded PDF not found or expired.")
