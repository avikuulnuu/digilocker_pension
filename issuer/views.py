"""DigiLocker Issuer API views."""

import logging
import time

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
    read_file_bytes,
    resolve_path,
)
from issuer.services.identity_validator import IdentityMismatchError
from issuer.services.response_builder import (
    build_error_response,
    build_success_response,
)
from issuer.services.xml_parser import XMLParseError, parse_pull_uri_request

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
    """POST /issuer/pull-uri — DigiLocker Pull URI Request API."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    start_time = time.monotonic()
    timestamp = timezone.now().isoformat()
    txn = ""
    log_data = {
        "request_ip": _get_client_ip(request),
        "user_agent": request.META.get("HTTP_USER_AGENT", ""),
    }

    try:
        raw_body = request.body

        # 1. Parse XML
        try:
            request_data = parse_pull_uri_request(raw_body)
        except XMLParseError as exc:
            logger.warning("XML parse error: %s", exc)
            return HttpResponse(
                build_error_response(timestamp, txn),
                content_type="application/xml",
                status=400,
            )

        txn = request_data.txn
        timestamp = request_data.timestamp
        log_data["txn_id"] = txn
        log_data["document_type"] = request_data.doc_type
        if request_data.udfs.get("UDF1"):
            log_data["authorization_number"] = request_data.udfs["UDF1"]
        log_data["digilocker_id"] = request_data.digilocker_id

        # 2. Authenticate
        hmac_header = request.META.get("HTTP_X_DIGILOCKER_HMAC", "")
        authenticate_request(
            raw_body, hmac_header,
            request_data.keyhash, request_data.timestamp, request_data.org_id,
        )

        # 3. Process: lookup → identity → URI → file → encode
        result = process_pull_uri(request_data)

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

        return HttpResponse(xml_response, content_type="application/xml", status=200)

    except AuthenticationError as exc:
        elapsed = int((time.monotonic() - start_time) * 1000)
        _log_access(log_data, None, 0, elapsed, str(exc))
        return HttpResponse(status=401)

    except (DocumentNotFoundError, IdentityMismatchError) as exc:
        elapsed = int((time.monotonic() - start_time) * 1000)
        _log_access(log_data, None, 0, elapsed, str(exc))
        return HttpResponse(
            build_error_response(timestamp, txn),
            content_type="application/xml",
            status=200,
        )

    except (FileNotAvailableError, IntegrityCheckError) as exc:
        elapsed = int((time.monotonic() - start_time) * 1000)
        _log_access(log_data, None, 0, elapsed, str(exc))
        return HttpResponse(
            build_error_response(timestamp, txn),
            content_type="application/xml",
            status=200,
        )

    except Exception:
        logger.exception("Unexpected error in pull_uri_view")
        elapsed = int((time.monotonic() - start_time) * 1000)
        _log_access(log_data, None, 0, elapsed, "Internal error")
        return HttpResponse(
            build_error_response(timestamp, txn),
            content_type="application/xml",
            status=500,
        )


@csrf_exempt
@ratelimit(key="ip", rate="60/m", method="GET", block=True)
def document_fetch_view(request, uri):
    """GET /issuer/document/<uri> — Fetch document PDF by URI."""
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])

    start_time = time.monotonic()
    log_data = {
        "request_ip": _get_client_ip(request),
        "user_agent": request.META.get("HTTP_USER_AGENT", ""),
        "requested_mobile": request.GET.get("mobile"),
    }

    try:
        # Authenticate via HMAC on empty body or query string
        hmac_header = request.META.get("HTTP_X_DIGILOCKER_HMAC", "")
        if not hmac_header:
            return HttpResponse(status=401)

        try:
            doc = Document.objects.get(uri=uri, is_active=True, digilocker_enabled=True)
        except Document.DoesNotExist:
            elapsed = int((time.monotonic() - start_time) * 1000)
            _log_access(log_data, None, 0, elapsed, f"URI not found: {uri}")
            return HttpResponse(status=404)

        log_data["authorization_number"] = doc.authorization_number
        log_data["document_type"] = doc.document_type
        log_data["file_path"] = doc.file_relative_path
        log_data["file_checksum"] = doc.file_checksum
        log_data["requested_mobile"] = request.GET.get("mobile") or doc.employee_mobile

        file_bytes = read_file_bytes(doc)

        elapsed = int((time.monotonic() - start_time) * 1000)
        _log_access(log_data, doc, 1, elapsed)

        response = HttpResponse(file_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="{doc.doc_id}.pdf"'
        return response

    except (FileNotAvailableError, IntegrityCheckError) as exc:
        elapsed = int((time.monotonic() - start_time) * 1000)
        _log_access(log_data, None, 0, elapsed, str(exc))
        return HttpResponse(status=410)

    except Exception:
        logger.exception("Unexpected error in document_fetch_view")
        return HttpResponse(status=500)


def _log_access(data: dict, doc, status: int, elapsed_ms: int, error: str = ""):
    """Write an access log entry."""
    try:
        AccessLog.objects.create(
            document=doc,
            authorization_number=data.get("authorization_number", ""),
            document_type=data.get("document_type", ""),
            txn_id=data.get("txn_id", ""),
            digilocker_id=data.get("digilocker_id", ""),
            request_ip=data.get("request_ip"),
            user_agent=data.get("user_agent", ""),
            requested_mobile=data.get("requested_mobile") or (getattr(doc, "employee_mobile", None) if doc else None),
            file_path=data.get("file_path") or (getattr(doc, "file_relative_path", "") if doc else ""),
            file_checksum=data.get("file_checksum") or (getattr(doc, "file_checksum", "") if doc else ""),
            response_status=status,
            error_message=error,
            processing_time_ms=elapsed_ms,
        )
    except Exception:
        logger.exception("Failed to write access log")
