"""DigiLocker Issuer API views."""

import logging
import time

from django.db.models import F
from django.http import HttpResponse, HttpResponseNotAllowed
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django_ratelimit.decorators import ratelimit

from issuer.authentication import authenticate_request, AuthenticationError
from issuer.models import AccessLog, Document
from issuer.services.document_service import (
    DocumentNotFoundError,
    process_pull_uri,
)
from issuer.services.file_service import (
    FileNotAvailableError,
    IntegrityCheckError,
)
from issuer.services.identity_validator import IdentityMismatchError
from issuer.services.response_builder import (
    build_error_response,
    build_success_response,
)
from issuer.services.pull_doc_log import (
    auth_failed,
    auth_ok,
    request_received,
    retrieval_failed,
    retrieval_success,
    stage_ok,
    xml_parse_failed,
    xml_parsed,
)
from issuer.services.xml_parser import XMLParseError, parse_pull_uri_request
from issuer.log_safety import safe_failure_reason

logger = logging.getLogger("issuer")


def _get_client_ip(request):
    """Extract client IP, respecting X-Forwarded-For behind a reverse proxy."""
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


@csrf_exempt
def pull_doc_disabled_view(request):
    """Reject legacy Pull Document Request API (removed in DLTS v1.13)."""
    logger.warning(
        "pull_doc.disabled: deprecated Pull Document API request | method=%s path=%s ip=%s",
        request.method,
        request.path,
        _get_client_ip(request),
    )
    return HttpResponse(
        "Pull Document Request API is not available. Use POST /api/pulluri instead.",
        status=404,
        content_type="text/plain",
    )


@csrf_exempt
@ratelimit(key="ip", rate="60/m", method="POST", block=True)
def pull_uri_view(request):
    """POST /api/pulluri — DigiLocker Pull URI Request API."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    start_time = time.monotonic()
    timestamp = timezone.now().isoformat()
    txn = ""
    request_ip = _get_client_ip(request)
    log_data = {
        "request_ip": request_ip,
        "user_agent": request.META.get("HTTP_USER_AGENT", ""),
    }
    request_received(
        endpoint="pull-uri",
        request_ip=request_ip,
        user_agent=log_data["user_agent"],
    )

    try:
        raw_body = request.body

        # 1. Parse XML
        try:
            request_data = parse_pull_uri_request(raw_body)
        except XMLParseError as exc:
            xml_parse_failed(error=str(exc), request_ip=request_ip)
            elapsed = int((time.monotonic() - start_time) * 1000)
            retrieval_failed(
                endpoint="pull-uri",
                stage="xml_parse",
                reason=str(exc),
                elapsed_ms=elapsed,
                request_ip=request_ip,
            )
            _log_access(log_data, None, 0, elapsed, str(exc))
            return HttpResponse(
                build_error_response(timestamp, txn),
                content_type="application/xml",
                status=400,
            )

        txn = request_data.txn
        timestamp = request_data.timestamp
        log_data["txn_id"] = txn
        log_data["document_type"] = request_data.doc_type
        if request_data.udfs.get("AUTHN"):
            log_data["authorization_number"] = request_data.udfs["AUTHN"]
        log_data["digilocker_id"] = request_data.digilocker_id
        xml_parsed(
            txn=txn,
            doc_type=request_data.doc_type,
            authorization_number=log_data.get("authorization_number", ""),
            digilocker_id=request_data.digilocker_id,
        )

        # 2. Authenticate
        hmac_header = request.META.get("HTTP_X_DIGILOCKER_HMAC", "")
        authenticate_request(
            raw_body, hmac_header,
            request_data.keyhash, request_data.timestamp, request_data.org_id,
        )
        auth_ok(txn=txn)

        # 3. Process: lookup → identity → URI → file → encode
        result = process_pull_uri(
            request_data,
            txn=txn,
            request_ip=request_ip,
            digilocker_id=request_data.digilocker_id,
        )

        # 4. Build success response
        xml_response = build_success_response(
            doc=result["doc"],
            uri=result["uri"],
            timestamp=timestamp,
            txn=txn,
            doc_content_b64=result["doc_content_b64"],
            data_content_b64=result["data_content_b64"],
        )

        elapsed = int((time.monotonic() - start_time) * 1000)
        _log_access(log_data, result["doc"], 1, elapsed)
        retrieval_success(
            endpoint="pull-uri",
            txn=txn,
            document_id=result["doc"].pk,
            uri=result["uri"],
            file_bytes=len(result["doc_content_b64"]),
            elapsed_ms=elapsed,
        )

        return HttpResponse(xml_response, content_type="application/xml", status=200)

    except AuthenticationError as exc:
        elapsed = int((time.monotonic() - start_time) * 1000)
        reason = safe_failure_reason(exc)
        auth_failed(txn=txn, reason=reason, request_ip=request_ip)
        retrieval_failed(
            endpoint="pull-uri",
            stage="auth",
            reason=reason,
            txn=txn,
            elapsed_ms=elapsed,
            request_ip=request_ip,
        )
        _log_access(log_data, None, 0, elapsed, str(exc))
        return HttpResponse(status=401)

    except DocumentNotFoundError as exc:
        elapsed = int((time.monotonic() - start_time) * 1000)
        retrieval_failed(
            endpoint="pull-uri",
            stage="lookup",
            reason=safe_failure_reason(exc),
            reason_code=getattr(exc, "reason_code", ""),
            txn=txn,
            elapsed_ms=elapsed,
            doc_type=log_data.get("document_type"),
            authorization_number=log_data.get("authorization_number"),
        )
        _log_access(log_data, None, 0, elapsed, str(exc))
        return HttpResponse(
            build_error_response(timestamp, txn),
            content_type="application/xml",
            status=200,
        )

    except IdentityMismatchError as exc:
        elapsed = int((time.monotonic() - start_time) * 1000)
        retrieval_failed(
            endpoint="pull-uri",
            stage="identity",
            reason=safe_failure_reason(exc),
            txn=txn,
            elapsed_ms=elapsed,
        )
        _log_access(log_data, None, 0, elapsed, str(exc))
        return HttpResponse(
            build_error_response(timestamp, txn),
            content_type="application/xml",
            status=200,
        )

    except FileNotAvailableError as exc:
        elapsed = int((time.monotonic() - start_time) * 1000)
        retrieval_failed(
            endpoint="pull-uri",
            stage="file_read",
            reason=safe_failure_reason(exc),
            txn=txn,
            elapsed_ms=elapsed,
        )
        _log_access(log_data, None, 0, elapsed, str(exc))
        return HttpResponse(
            build_error_response(timestamp, txn),
            content_type="application/xml",
            status=200,
        )

    except IntegrityCheckError as exc:
        elapsed = int((time.monotonic() - start_time) * 1000)
        retrieval_failed(
            endpoint="pull-uri",
            stage="integrity",
            reason=safe_failure_reason(exc),
            txn=txn,
            elapsed_ms=elapsed,
        )
        _log_access(log_data, None, 0, elapsed, str(exc))
        return HttpResponse(
            build_error_response(timestamp, txn),
            content_type="application/xml",
            status=200,
        )

    except Exception:
        elapsed = int((time.monotonic() - start_time) * 1000)
        logger.exception("Unexpected error in pull_uri_view")
        retrieval_failed(
            endpoint="pull-uri",
            stage="internal",
            reason="Internal error",
            txn=txn,
            elapsed_ms=elapsed,
        )
        _log_access(log_data, None, 0, elapsed, "Internal error")
        return HttpResponse(
            build_error_response(timestamp, txn),
            content_type="application/xml",
            status=500,
        )


@csrf_exempt
def document_fetch_disabled_view(request, uri=""):
    """Reject public document fetch by URI — PDF is served via Pull URI response only."""
    logger.warning(
        "document_fetch.disabled: rejected request | method=%s path=%s uri=%s ip=%s",
        request.method,
        request.path,
        uri,
        _get_client_ip(request),
    )
    return HttpResponse(
        "Document fetch by URI is not available. Use POST /api/pulluri with format=both or format=pdf.",
        status=404,
        content_type="text/plain",
    )


def _log_access(data: dict, doc, status: int, elapsed_ms: int, error: str = ""):
    """Write an access log entry and update document access stats on success."""
    try:
        doc_type_val = data.get("document_type", "") or ""
        if len(doc_type_val) > 30:
            logger.warning(
                "document_type length (%d) exceeds DB max (30)",
                len(doc_type_val),
            )
            doc_type_val = doc_type_val[:30]
        AccessLog.objects.create(
            document=doc,
            authorization_number=data.get("authorization_number", ""),
            document_type=doc_type_val,
            txn_id=data.get("txn_id", ""),
            digilocker_id=data.get("digilocker_id", ""),
            request_ip=data.get("request_ip"),
            user_agent=data.get("user_agent", ""),
            requested_mobile=data.get("requested_mobile") or (getattr(doc, "employee_mobile", None) if doc else None),
            file_path=data.get("file_path") or (getattr(doc, "file_name", "") if doc else ""),
            file_checksum=(data.get("file_checksum") or (getattr(doc, "file_checksum", "") if doc else "") or ""),
            response_status=status,
            error_message=error,
            processing_time_ms=elapsed_ms,
        )
        if doc is not None and status == 1:
            Document.objects.filter(pk=doc.pk).update(
                access_count=F("access_count") + 1,
                last_accessed_at=timezone.now(),
            )
    except Exception:
        logger.exception("Failed to write access log")
