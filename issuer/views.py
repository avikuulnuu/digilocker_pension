"""DigiLocker Issuer API views."""

import base64
import hashlib
import hmac
import logging
import time

from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed
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
    read_file_bytes,
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
@ratelimit(key="ip", rate="60/m", method="GET", block=True)
def document_fetch_view(request, uri):
    """GET /api/document/<uri> — Fetch document PDF by URI."""
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])

    start_time = time.monotonic()
    request_ip = _get_client_ip(request)
    log_data = {
        "request_ip": request_ip,
        "user_agent": request.META.get("HTTP_USER_AGENT", ""),
        "requested_mobile": request.GET.get("mobile"),
    }
    request_received(endpoint="document-fetch", request_ip=request_ip, user_agent=log_data["user_agent"])

    try:
        # Authenticate via HMAC on empty body or query string
        hmac_header = request.META.get("HTTP_X_DIGILOCKER_HMAC", "")
        if not hmac_header:
            elapsed = int((time.monotonic() - start_time) * 1000)
            auth_failed(reason="Missing X-DigiLocker-HMAC header", request_ip=request_ip)
            retrieval_failed(
                endpoint="document-fetch",
                stage="auth",
                reason="Missing HMAC header",
                uri=uri,
                elapsed_ms=elapsed,
            )
            _log_access(log_data, None, 0, elapsed, "Missing HMAC header")
            return HttpResponse(status=401)

        try:
            doc = Document.objects.get(digilocker_uri=uri, is_active=True, digilocker_enabled=True)
        except Document.DoesNotExist:
            elapsed = int((time.monotonic() - start_time) * 1000)
            retrieval_failed(
                endpoint="document-fetch",
                stage="lookup",
                reason="URI_NOT_FOUND",
                uri=uri,
                elapsed_ms=elapsed,
            )
            _log_access(log_data, None, 0, elapsed, f"URI not found: {uri}")
            return HttpResponse(status=404)

        log_data["authorization_number"] = doc.authorization_number
        log_data["document_type"] = doc.document_type
        log_data["file_path"] = doc.file_name
        log_data["file_checksum"] = doc.file_checksum
        log_data["requested_mobile"] = request.GET.get("mobile") or doc.employee_mobile
        stage_ok(
            "lookup",
            "Document resolved by URI",
            document_id=doc.pk,
            uri=uri,
            authorization_number=doc.authorization_number,
        )

        file_bytes = read_file_bytes(doc, request_ip=request_ip)

        elapsed = int((time.monotonic() - start_time) * 1000)
        _log_access(log_data, doc, 1, elapsed)
        retrieval_success(
            endpoint="document-fetch",
            document_id=doc.pk,
            uri=uri,
            file_bytes=len(file_bytes),
            elapsed_ms=elapsed,
        )

        response = HttpResponse(file_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="{doc.digilocker_doc_id}.pdf"'
        return response

    except FileNotAvailableError as exc:
        elapsed = int((time.monotonic() - start_time) * 1000)
        retrieval_failed(
            endpoint="document-fetch",
            stage="file_read",
            reason=safe_failure_reason(exc),
            uri=uri,
            elapsed_ms=elapsed,
        )
        _log_access(log_data, None, 0, elapsed, str(exc))
        return HttpResponse(status=410)

    except IntegrityCheckError as exc:
        elapsed = int((time.monotonic() - start_time) * 1000)
        retrieval_failed(
            endpoint="document-fetch",
            stage="integrity",
            reason=safe_failure_reason(exc),
            uri=uri,
            elapsed_ms=elapsed,
        )
        _log_access(log_data, None, 0, elapsed, str(exc))
        return HttpResponse(status=410)

    except Exception:
        elapsed = int((time.monotonic() - start_time) * 1000)
        logger.exception("Unexpected error in document_fetch_view")
        retrieval_failed(
            endpoint="document-fetch",
            stage="internal",
            reason="Internal error",
            uri=uri,
            elapsed_ms=elapsed,
        )
        _log_access(log_data, None, 0, elapsed, "Internal error")
        return HttpResponse(status=500)


def _log_access(data: dict, doc, status: int, elapsed_ms: int, error: str = ""):
    """Write an access log entry."""
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
    except Exception:
        logger.exception("Failed to write access log")
