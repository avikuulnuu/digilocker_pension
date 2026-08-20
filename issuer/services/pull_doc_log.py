"""Structured logging for Pull URI and document fetch flows."""

import logging

from django.conf import settings

from issuer.log_safety import sanitize_log_context

logger = logging.getLogger("issuer")


def _context(**kwargs):
    parts = []
    for key, value in sanitize_log_context(**kwargs).items():
        parts.append(f"{key}={value}")
    return " ".join(parts)


def _log(level, event, message="", **context):
    ctx = _context(**context)
    if ctx:
        logger.log(level, "pull_doc.%s: %s | %s", event, message, ctx)
    else:
        logger.log(level, "pull_doc.%s: %s", event, message)


def request_received(*, endpoint, request_ip="", user_agent=""):
    _log(
        logging.INFO,
        "request_received",
        "Incoming request",
        endpoint=endpoint,
        request_ip=request_ip,
        user_agent=(user_agent or "")[:120],
    )


def xml_parsed(*, txn="", doc_type="", authorization_number="", digilocker_id=""):
    _log(
        logging.INFO,
        "xml_parsed",
        "PullURI XML parsed",
        txn=txn,
        doc_type=doc_type,
        authorization_number=authorization_number,
        digilocker_id=digilocker_id,
    )


def xml_parse_failed(*, error="", request_ip=""):
    _log(logging.WARNING, "xml_parse_failed", error, request_ip=request_ip)


def auth_ok(*, txn=""):
    _log(logging.INFO, "auth_ok", "Request authenticated", txn=txn)


def auth_failed(*, txn="", reason="", request_ip=""):
    _log(logging.WARNING, "auth_failed", reason, txn=txn, request_ip=request_ip)


def request_format_diagnostics(
    *, txn="", requested_format="", doc_content_included=False
):
    if not settings.ISSUER_VERBOSE_LOGGING:
        return
    _log(
        logging.DEBUG,
        "request_format",
        "PullURI response format selected",
        txn=txn,
        requested_format=requested_format,
        doc_content_included=doc_content_included,
    )


def stage_ok(stage, message="", **context):
    _log(logging.INFO, f"{stage}_ok", message, **context)


def stage_failed(stage, reason, **context):
    _log(logging.WARNING, f"{stage}_failed", reason, **context)


def retrieval_success(*, endpoint, txn="", document_id="", uri="", file_bytes=0, elapsed_ms=0):
    _log(
        logging.INFO,
        "retrieval_success",
        "Document retrieved successfully",
        endpoint=endpoint,
        txn=txn,
        document_id=document_id,
        uri=uri,
        file_bytes=file_bytes,
        elapsed_ms=elapsed_ms,
    )


def retrieval_failed(*, endpoint, stage, reason, txn="", elapsed_ms=0, **context):
    _log(
        logging.WARNING,
        "retrieval_failed",
        reason,
        endpoint=endpoint,
        stage=stage,
        txn=txn,
        elapsed_ms=elapsed_ms,
        **context,
    )
