"""Redact sensitive values before they reach application logs."""

from __future__ import annotations

import os

DROPPED_CONTEXT_KEYS = frozenset(
    {
        "request_name",
        "stored_name",
        "received_hmac",
        "computed_hmac",
        "body_b64",
    }
)

MASKED_IDENTIFIER_KEYS = frozenset(
    {
        "authorization_number",
        "digilocker_id",
        "uri",
        "requested_mobile",
        "mobile",
        "org_id",
        "received_org_id",
    }
)

PATH_KEYS = frozenset(
    {
        "file_path",
        "path",
        "expected_path",
        "tried_paths",
        "file_name",
    }
)


def mask_identifier(value: str, *, visible_tail: int = 4) -> str:
    text = str(value).strip()
    if not text:
        return ""
    if len(text) <= visible_tail:
        return "***"
    return f"***{text[-visible_tail:]}"


def mask_path(value: str) -> str:
    text = str(value).strip()
    if not text:
        return ""
    if "," in text:
        return ", ".join(mask_path(part) for part in text.split(","))
    basename = os.path.basename(text.replace("\\", "/"))
    return basename or "***"


def sanitize_log_value(key: str, value):
    if value is None or value == "":
        return None
    if key in DROPPED_CONTEXT_KEYS:
        return None
    if key in MASKED_IDENTIFIER_KEYS:
        return mask_identifier(str(value))
    if key in PATH_KEYS:
        return mask_path(str(value))
    return value


def sanitize_log_context(**context) -> dict:
    sanitized = {}
    for key, value in context.items():
        clean = sanitize_log_value(key, value)
        if clean is not None and clean != "":
            sanitized[key] = clean
    return sanitized


def safe_failure_reason(exc: BaseException) -> str:
    """Return a log-safe failure label without PII from exception text."""
    code = getattr(exc, "reason_code", "")
    if code:
        return str(code)
    return type(exc).__name__
