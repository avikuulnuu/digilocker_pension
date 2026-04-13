"""Identity validation — match requester identity against document owner."""

import logging
import re
import unicodedata

from django.conf import settings

from issuer.models import Document

logger = logging.getLogger("issuer")


class IdentityMismatchError(Exception):
    pass


def _normalize_name(name: str) -> str:
    """Lowercase, strip spaces/punctuation, normalize unicode."""
    name = unicodedata.normalize("NFKD", name)
    name = re.sub(r"[^a-z0-9]", "", name.lower())
    return name


def _parse_dob(dob_str: str):
    """Parse DD-MM-YYYY date string."""
    from datetime import datetime
    try:
        return datetime.strptime(dob_str, "%d-%m-%Y").date()
    except (ValueError, TypeError):
        return None


def validate_identity(doc: Document, full_name: str = "", dob: str = "") -> None:
    """Validate requester identity against document owner fields.

    In STRICT mode: at least one identity field must be provided,
    and all provided fields must match.
    In LENIENT mode: validation only runs if fields are provided.
    """
    mode = settings.DIGILOCKER_IDENTITY_VALIDATION_MODE
    has_name = bool(full_name.strip())
    has_dob = bool(dob.strip())

    if mode == "STRICT" and not has_name and not has_dob:
        logger.info("STRICT mode: no identity fields provided, rejecting")
        raise IdentityMismatchError(
            "Identity validation requires at least name or DOB"
        )

    # Validate name if provided
    if has_name and doc.employee_name:
        if _normalize_name(full_name) != _normalize_name(doc.employee_name):
            logger.info(
                "Name mismatch for doc %d: request=%s stored=%s",
                doc.pk, full_name, doc.employee_name,
            )
            raise IdentityMismatchError("Name does not match document owner")

    # Validate DOB if provided
    if has_dob and doc.employee_dob:
        request_dob = _parse_dob(dob)
        if request_dob is None:
            raise IdentityMismatchError("Invalid DOB format (expected DD-MM-YYYY)")
        if request_dob != doc.employee_dob:
            logger.info("DOB mismatch for doc %d", doc.pk)
            raise IdentityMismatchError("DOB does not match document owner")
