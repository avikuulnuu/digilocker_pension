"""Identity validation — match requester identity against document owner."""

import logging
import re
import unicodedata
from difflib import SequenceMatcher

from django.conf import settings

from issuer.models import Document
from issuer.services.pull_doc_log import stage_failed

logger = logging.getLogger("issuer")


class IdentityMismatchError(Exception):
    pass


def _normalize_name(name: str) -> str:
    """Lowercase, strip spaces/punctuation, normalize unicode."""
    name = unicodedata.normalize("NFKD", name)
    name = re.sub(r"[^a-z0-9]", "", name.lower())
    return name


def _name_match_ratio(request_name: str, stored_name: str) -> float:
    """Similarity score in [0, 1] between normalized request and stored names."""
    a = _normalize_name(request_name)
    b = _normalize_name(stored_name)
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _required_match_ratio(mode: str) -> float:
    if mode == "LENIENT":
        return settings.DIGILOCKER_LENIENT_NAME_MATCH_THRESHOLD
    return 1.0


def validate_identity(doc: Document, full_name: str = "", dob: str = "") -> None:
    """Validate requester identity against document owner fields.

    STRICT: name required; normalized name must match exactly.
    LENIENT: name optional; when provided, must meet DIGILOCKER_LENIENT_NAME_MATCH_THRESHOLD.

    DOB is accepted for backward compatibility but is not used for request-time
    validation because document DOB is now optional in storage and request flow.
    """
    mode = settings.DIGILOCKER_IDENTITY_VALIDATION_MODE
    has_name = bool(full_name.strip())

    if mode == "STRICT" and not has_name:
        stage_failed(
            "identity",
            "STRICT mode: no name provided",
            document_id=doc.pk,
            mode=mode,
        )
        raise IdentityMismatchError("Identity validation requires name")

    if has_name and doc.employee_name:
        ratio = _name_match_ratio(full_name, doc.employee_name)
        required = _required_match_ratio(mode)

        if ratio < required:
            similarity_pct = round(ratio * 100, 1)
            required_pct = round(required * 100, 1)
            logger.warning(
                "pull_doc.identity: name mismatch (mode=%s similarity=%s%% required=%s%% doc_id=%s)",
                mode,
                similarity_pct,
                required_pct,
                doc.pk,
            )
            stage_failed(
                "identity",
                "IDENTITY_MISMATCH",
                document_id=doc.pk,
                mode=mode,
                similarity_pct=similarity_pct,
                required_pct=required_pct,
            )
            if mode == "LENIENT":
                raise IdentityMismatchError(
                    f"Name does not match document owner "
                    f"(similarity {similarity_pct}%, required {required_pct}%)"
                )
            raise IdentityMismatchError("Name does not match document owner")
