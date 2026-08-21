"""Persistence helpers for Pull URI request outcomes."""

import ipaddress
import logging

from django.db.models import F
from django.utils import timezone

from issuer.models import AccessLog, Document

logger = logging.getLogger("issuer")

_FIELD_LIMITS = {
    "authorization_number": 50,
    "document_type": 30,
    "txn_id": 100,
    "digilocker_id": 255,
    "requested_mobile": 10,
    "file_checksum": 64,
    "reason_code": 50,
    "processing_stage": 20,
}


def _bounded(value, field_name):
    text = str(value or "")
    limit = _FIELD_LIMITS[field_name]
    return text[:limit]


def _valid_ip(value):
    if not value:
        return None
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return None


def start_access_log(*, request_ip=None, user_agent=""):
    """Create the audit row for a POST that entered the Pull URI view."""
    try:
        return AccessLog.objects.create(
            request_ip=_valid_ip(request_ip),
            user_agent=str(user_agent or ""),
        )
    except Exception:
        logger.exception("Failed to start access log")
        return None


def finalize_access_log(
    access_log,
    *,
    data=None,
    document=None,
    response_status=0,
    outcome_class=AccessLog.OutcomeClass.LEGACY_UNCLASSIFIED,
    reason_code="",
    processing_stage="",
    http_status_code=None,
    elapsed_ms=None,
    error_message="",
):
    """Finalize an existing audit row and update served-document counters."""
    if access_log is None:
        return

    values = data or {}
    try:
        access_log.document = document
        access_log.authorization_number = _bounded(
            values.get("authorization_number"), "authorization_number"
        )
        access_log.document_type = _bounded(
            values.get("document_type"), "document_type"
        )
        access_log.txn_id = _bounded(values.get("txn_id"), "txn_id")
        access_log.digilocker_id = _bounded(
            values.get("digilocker_id"), "digilocker_id"
        )
        access_log.requested_mobile = _bounded(
            values.get("requested_mobile")
            or (getattr(document, "employee_mobile", None) if document else ""),
            "requested_mobile",
        ) or None
        access_log.file_path = str(
            values.get("file_path")
            or (getattr(document, "file_name", "") if document else "")
            or ""
        )
        access_log.file_checksum = _bounded(
            values.get("file_checksum")
            or (getattr(document, "file_checksum", "") if document else ""),
            "file_checksum",
        )
        access_log.response_status = response_status
        access_log.outcome_class = outcome_class
        access_log.reason_code = _bounded(reason_code, "reason_code")
        access_log.processing_stage = _bounded(processing_stage, "processing_stage")
        access_log.http_status_code = http_status_code
        access_log.error_message = str(error_message or "")
        access_log.processing_time_ms = elapsed_ms
        access_log.save()

        if document is not None and response_status == 1:
            Document.objects.filter(pk=document.pk).update(
                access_count=F("access_count") + 1,
                last_accessed_at=timezone.now(),
            )
    except Exception:
        logger.exception("Failed to finalize access log")
