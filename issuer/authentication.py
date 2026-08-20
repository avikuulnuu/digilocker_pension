"""HMAC and KeyHash authentication for DigiLocker requests."""

import base64
import hashlib
import hmac as hmac_mod
import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger("issuer")

UTF8_BOM = b"\xef\xbb\xbf"
HMAC_ENCODING_STANDARD = "STANDARD"
HMAC_ENCODING_DIGILOCKER_HEX = "DIGILOCKER_HEX"


class AuthenticationError(Exception):
    """Raised when DigiLocker request authentication fails."""


def _hmac_signature(api_key: bytes, body: bytes) -> str:
    return base64.b64encode(
        hmac_mod.new(api_key, body, hashlib.sha256).digest()
    ).decode("ascii")


def _digilocker_hex_hmac_signature(api_key: bytes, body: bytes) -> str:
    digest_hex = hmac_mod.new(api_key, body, hashlib.sha256).hexdigest()
    return base64.b64encode(digest_hex.encode("ascii")).decode("ascii")


def _configured_hmac_signature(api_key: bytes, body: bytes) -> str:
    mode = settings.DIGILOCKER_HMAC_ENCODING_MODE
    if mode == HMAC_ENCODING_STANDARD:
        return _hmac_signature(api_key, body)
    if mode == HMAC_ENCODING_DIGILOCKER_HEX:
        return _digilocker_hex_hmac_signature(api_key, body)

    logger.error("Invalid HMAC encoding mode configured: %s", mode)
    raise AuthenticationError("Invalid HMAC encoding configuration")


def _signature_matches(api_key: bytes, body: bytes, received_hmac: str) -> bool:
    return hmac_mod.compare_digest(
        _configured_hmac_signature(api_key, body),
        received_hmac,
    )


def _log_hmac_diagnostics(
    raw_body: bytes,
    received_hmac: str,
    api_key: bytes,
) -> None:
    if not settings.ISSUER_VERBOSE_LOGGING:
        return

    stripped_hmac = received_hmac.strip()
    try:
        decoded_hmac = base64.b64decode(stripped_hmac, validate=True)
        expected_length = (
            hashlib.sha256().digest_size * 2
            if settings.DIGILOCKER_HMAC_ENCODING_MODE == HMAC_ENCODING_DIGILOCKER_HEX
            else hashlib.sha256().digest_size
        )
        valid_hmac_base64 = len(decoded_hmac) == expected_length
    except (ValueError, UnicodeEncodeError):
        valid_hmac_base64 = False

    without_bom = raw_body[len(UTF8_BOM):] if raw_body.startswith(UTF8_BOM) else raw_body
    without_final_newline = raw_body
    if raw_body.endswith(b"\r\n"):
        without_final_newline = raw_body[:-2]
    elif raw_body.endswith(b"\n"):
        without_final_newline = raw_body[:-1]

    logger.debug(
        "HMAC diagnostics: mode=%s body_len=%d header_len=%d valid_base64=%s "
        "header_whitespace=%s utf8_bom=%s final_newline=%s crlf_count=%d "
        "lf_count=%d matches_trimmed_header=%s matches_without_bom=%s "
        "matches_without_final_newline=%s matches_crlf_to_lf=%s",
        settings.DIGILOCKER_HMAC_ENCODING_MODE,
        len(raw_body),
        len(received_hmac),
        valid_hmac_base64,
        stripped_hmac != received_hmac,
        raw_body.startswith(UTF8_BOM),
        raw_body.endswith((b"\r\n", b"\n")),
        raw_body.count(b"\r\n"),
        raw_body.count(b"\n"),
        _signature_matches(api_key, raw_body, stripped_hmac),
        without_bom != raw_body
        and _signature_matches(api_key, without_bom, received_hmac),
        without_final_newline != raw_body
        and _signature_matches(api_key, without_final_newline, received_hmac),
        b"\r\n" in raw_body
        and _signature_matches(api_key, raw_body.replace(b"\r\n", b"\n"), received_hmac),
    )


def verify_hmac(raw_body: bytes, received_hmac: str) -> None:
    """Verify x-digilocker-hmac header against request body.

    Uses constant-time comparison to prevent timing attacks.
    """
    api_key = settings.DIGILOCKER_API_KEY.encode("utf-8")
    computed = _configured_hmac_signature(api_key, raw_body)

    if not hmac_mod.compare_digest(computed, received_hmac):
        logger.warning("HMAC verification failed (body_len=%d)", len(raw_body))
        _log_hmac_diagnostics(raw_body, received_hmac, api_key)
        raise AuthenticationError("Invalid HMAC signature")


def verify_keyhash(keyhash: str, timestamp_str: str) -> None:
    """Verify KeyHash = SHA256(API_KEY + timestamp)."""
    api_key = settings.DIGILOCKER_API_KEY
    expected = hashlib.sha256((api_key + timestamp_str).encode("utf-8")).hexdigest()
    if not hmac_mod.compare_digest(expected, keyhash):
        logger.warning("KeyHash verification failed")
        raise AuthenticationError("Invalid KeyHash")


def verify_timestamp(timestamp_str: str) -> None:
    """Reject requests outside the allowed timestamp skew window."""
    from django.utils.dateparse import parse_datetime

    request_time = parse_datetime(timestamp_str)
    if request_time is None:
        raise AuthenticationError("Invalid timestamp format")

    now = timezone.now()
    skew = timedelta(seconds=settings.DIGILOCKER_TIMESTAMP_SKEW_SECONDS)
    if abs(now - request_time) > skew:
        logger.warning("Request timestamp outside allowed skew window")
        raise AuthenticationError("Request timestamp expired or too far in the future")


def authenticate_request(raw_body: bytes, hmac_header: str, keyhash: str,
                         timestamp_str: str, org_id: str) -> None:
    """Run all authentication checks on an incoming DigiLocker request."""
    if not hmac_header:
        raise AuthenticationError("Missing x-digilocker-hmac header")

    verify_hmac(raw_body, hmac_header)
    verify_keyhash(keyhash, timestamp_str)
    # verify_timestamp(timestamp_str) # Optional: enable if you want to enforce timestamp validity

    if org_id and org_id != settings.DIGILOCKER_ISSUER_ID:
        logger.warning("orgId mismatch for request")
        raise AuthenticationError("orgId does not match issuer")
