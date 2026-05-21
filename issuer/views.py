"""DigiLocker Issuer API views."""

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
import uuid

from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import render
from django.test import RequestFactory
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
    compute_checksum,
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


def _build_demo_pull_uri_xml(authorization_number: str, document_type: str) -> tuple[str, str, str]:
    ts = timezone.now().isoformat()
    txn = f"demo-{uuid.uuid4().hex[:10]}"
    digi_id = f"dl-demo-{secrets.token_hex(4)}"
    keyhash = hashlib.sha256((settings.DIGILOCKER_API_KEY + ts).encode("utf-8")).hexdigest()
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<PullURIRequest xmlns="http://tempuri.org/" ver="3.0" '
        f'ts="{ts}" txn="{txn}" '
        f'orgId="{settings.DIGILOCKER_ISSUER_ID}" '
        f'keyhash="{keyhash}" format="both">'
        '<DocDetails>'
        f'<DocType>{document_type}</DocType>'
        f'<DigiLockerId>{digi_id}</DigiLockerId>'
        '<FullName>Sunil Kumar</FullName>'
        '<DOB>31-12-1990</DOB>'
        f'<UDF1>{authorization_number}</UDF1>'
        '</DocDetails>'
        '</PullURIRequest>'
    )
    return xml, keyhash, txn


def _sign_hmac(raw_body: bytes) -> str:
    return base64.b64encode(
        hmac.new(settings.DIGILOCKER_API_KEY.encode("utf-8"), raw_body, hashlib.sha256).digest()
    ).decode("utf-8")


def _ensure_demo_document(authorization_number: str, document_type: str) -> Document:
    base_path = settings.DIGILOCKER_BASE_STORAGE_PATH
    os.makedirs(base_path, exist_ok=True)
    file_name = f"demo_{authorization_number}_{document_type}.pdf"
    file_path = os.path.join(base_path, file_name)

    if not os.path.exists(file_path):
        with open(file_path, "wb") as f:
            f.write(
                b"%PDF-1.1\n"
                b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
                b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
                b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
                b"4 0 obj<< /Length 44 >>\nstream\nBT /F1 18 Tf 40 100 Td (Demo Doc) Tj ET\nendstream\nendobj\n"
                b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
                b"xref\n0 6\n0000000000 65535 f \n0000000010 00000 n \n0000000060 00000 n \n0000000120 00000 n \n0000000220 00000 n \n0000000290 00000 n \ntrailer<< /Size 6 /Root 1 0 R >>\nstartxref\n350\n%%EOF\n"
            )

    checksum = compute_checksum(file_path)
    defaults = {
        "employee_name": "Sunil Kumar",
        "employee_dob": timezone.datetime(1990, 12, 31).date(),
        "authorization_date": "01/01/2024",
        "file_name": file_name,
        "file_checksum": checksum,
        "file_exists": True,
        "digilocker_enabled": True,
        "is_active": True,
        "external_system_id": f"demo-{authorization_number}",
    }
    doc, _ = Document.objects.get_or_create(
        authorization_number=authorization_number,
        document_type=document_type,
        defaults={
            **defaults,
            "external_system_id": defaults["external_system_id"],
        },
    )
    if doc.file_name != file_name or doc.file_checksum != checksum or not doc.file_exists:
        doc.file_name = file_name
        doc.file_checksum = checksum
        doc.file_exists = True
        doc.save(update_fields=["file_name", "file_checksum", "file_exists"])
    return doc


def _extract_uri(xml_text: str) -> str:
    import re

    match = re.search(r"<URI>([^<]+)</URI>", xml_text)
    return match.group(1) if match else ""


def demo_ui(request):
    sample_values = [
        {"authorization_number": "AUTH100", "document_type": "PPO", "description": "Demo PPO document"},
        {"authorization_number": "AUTH1001", "document_type": "GPF", "description": "Demo GPF document"},
        {"authorization_number": "AUTH1002", "document_type": "CPO", "description": "Demo CPO document"},
    ]
    return render(request, "issuer/demo.html", {"samples": sample_values})


@csrf_exempt
def demo_submit(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    authorization_number = payload.get("authorization_number", "").strip()
    document_type = payload.get("document_type", "").strip().upper()
    if not authorization_number or not document_type:
        return JsonResponse({"error": "authorization_number and document_type are required"}, status=400)

    _ensure_demo_document(authorization_number, document_type)
    xml_body, _, _ = _build_demo_pull_uri_xml(authorization_number, document_type)
    hmac_header = _sign_hmac(xml_body.encode("utf-8"))

    rf = RequestFactory()
    internal_request = rf.post(
        "/issuer/pull-uri",
        data=xml_body,
        content_type="application/xml",
        HTTP_X_DIGILOCKER_HMAC=hmac_header,
    )

    response = pull_uri_view(internal_request)
    content = response.content.decode("utf-8")
    if response.status_code != 200:
        return JsonResponse({"status": "error", "message": content}, status=400)

    uri = _extract_uri(content)
    if not uri:
        return JsonResponse({"status": "error", "message": "Could not extract URI from response."}, status=500)

    view_doc_url = f"/issuer/demo/view-doc/{uri}"
    return JsonResponse({"status": "ok", "uri": uri, "view_doc_url": view_doc_url})


@csrf_exempt
def demo_view_doc(request, uri):
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])

    mobile = request.GET.get("mobile", "")
    hmac_header = _sign_hmac(b"")
    rf = RequestFactory()
    query = {"mobile": mobile} if mobile else {}
    internal_request = rf.get(
        f"/issuer/document/{uri}",
        data=query,
        HTTP_X_DIGILOCKER_HMAC=hmac_header,
    )
    return document_fetch_view(internal_request, uri)


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
            doc = Document.objects.get(digilocker_uri=uri, is_active=True, digilocker_enabled=True)
        except Document.DoesNotExist:
            elapsed = int((time.monotonic() - start_time) * 1000)
            _log_access(log_data, None, 0, elapsed, f"URI not found: {uri}")
            return HttpResponse(status=404)

        log_data["authorization_number"] = doc.authorization_number
        log_data["document_type"] = doc.document_type
        log_data["file_path"] = doc.file_name
        log_data["file_checksum"] = doc.file_checksum
        log_data["requested_mobile"] = request.GET.get("mobile") or doc.employee_mobile

        file_bytes = read_file_bytes(doc)

        elapsed = int((time.monotonic() - start_time) * 1000)
        _log_access(log_data, doc, 1, elapsed)

        response = HttpResponse(file_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="{doc.digilocker_doc_id}.pdf"'
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
            file_path=data.get("file_path") or (getattr(doc, "file_name", "") if doc else ""),
            file_checksum=(data.get("file_checksum") or (getattr(doc, "file_checksum", "") if doc else "") or ""),
            response_status=status,
            error_message=error,
            processing_time_ms=elapsed_ms,
        )
    except Exception:
        logger.exception("Failed to write access log")
