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


def validate_identity(doc: Document, full_name: str = "", dob: str = "") -> None:
    """Validate requester identity against document owner fields.

    In STRICT mode: name must be provided and match when stored.
    In LENIENT mode: name validation only runs if provided.

    DOB is accepted for backward compatibility but is not used for request-time
    validation because document DOB is now optional in storage and request flow.
    """
    mode = settings.DIGILOCKER_IDENTITY_VALIDATION_MODE
    has_name = bool(full_name.strip())

    if mode == "STRICT" and not has_name:
        logger.info("STRICT mode: no name provided, rejecting")
        raise IdentityMismatchError("Identity validation requires name")

    # Validate name if provided
    if has_name and doc.employee_name:
        if _normalize_name(full_name) != _normalize_name(doc.employee_name):
            logger.info(
                "Name mismatch for doc %d: request=%s stored=%s",
                doc.pk, full_name, doc.employee_name,
            )
            raise IdentityMismatchError("Name does not match document owner")

