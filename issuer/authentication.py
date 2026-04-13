"""HMAC and KeyHash authentication for DigiLocker requests."""

import base64
import hashlib
import hmac as hmac_mod
import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger("issuer")


class AuthenticationError(Exception):
    """Raised when DigiLocker request authentication fails."""


def verify_hmac(raw_body: bytes, received_hmac: str) -> None:
    """Verify x-digilocker-hmac header against request body.

    Uses constant-time comparison to prevent timing attacks.
    """
    api_key = settings.DIGILOCKER_API_KEY.encode("utf-8")
    computed = base64.b64encode(
        hmac_mod.new(api_key, raw_body, hashlib.sha256).digest()
    ).decode("utf-8")

    if not hmac_mod.compare_digest(computed, received_hmac):
        logger.warning("HMAC verification failed")
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
        logger.warning("Request timestamp outside allowed skew: %s", timestamp_str)
        raise AuthenticationError("Request timestamp expired or too far in the future")


def authenticate_request(raw_body: bytes, hmac_header: str, keyhash: str,
                         timestamp_str: str, org_id: str) -> None:
    """Run all authentication checks on an incoming DigiLocker request."""
    if not hmac_header:
        raise AuthenticationError("Missing x-digilocker-hmac header")

    verify_hmac(raw_body, hmac_header)
    verify_keyhash(keyhash, timestamp_str)
    verify_timestamp(timestamp_str)

    if org_id and org_id != settings.DIGILOCKER_ISSUER_ID:
        logger.warning("orgId mismatch: received=%s expected=%s", org_id, settings.DIGILOCKER_ISSUER_ID)
        raise AuthenticationError("orgId does not match issuer")
