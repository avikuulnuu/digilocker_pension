"""Read-only management UI for Document, AccessLog, and IntegrityLog."""

import base64
import csv
import mimetypes
import os
import secrets
from datetime import datetime
from io import StringIO

from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Count
from django.http import Http404, HttpResponse
from django.utils import timezone
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from issuer.kpi_report import (
    KPI_MIN_DATE,
    build_kpi_report,
    export_kpi_csv,
    kpi_definitions,
    parse_period,
    previous_month_range,
)
from issuer.manage_filters import (
    ACCESSLOG_FILTER_FIELDS,
    DOCUMENT_FILTER_FIELDS,
    INTEGRITYLOG_FILTER_FIELDS,
    accesslog_filter_choices,
    build_filter_query,
    document_filter_choices,
    filter_access_logs,
    filter_documents,
    filter_integrity_logs,
    get_filter_params,
    integritylog_filter_choices,
)
from issuer.models import AccessLog, Document, IntegrityLog
from issuer.services.base64_pdf import decode_pdf_bytes
from issuer.services.file_service import (
    diagnose_document_file,
    effective_file_name,
    find_readable_path,
    resolve_path,
)

PAGE_SIZE = 25


def _paginate(request, queryset):
    paginator = Paginator(queryset, PAGE_SIZE)
    page_number = request.GET.get("page", 1)
    return paginator.get_page(page_number)


def _serialize_export_value(value):
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return str(value)
    return value


def _export_csv(filename, fieldnames, rows):
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: _serialize_export_value(v) for k, v in row.items()})
    response = HttpResponse(buffer.getvalue(), content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _get_dashboard_stats():
    today = timezone.localdate()
    access_logs = AccessLog.objects.all()
    integrity_logs = IntegrityLog.objects.all()
    documents = Document.objects.all()

    served = access_logs.filter(response_status=1)
    errors = access_logs.exclude(response_status=1)

    return {
        "documents_total": documents.count(),
        "documents_active": documents.filter(is_active=True).count(),
        "documents_enabled": documents.filter(digilocker_enabled=True).count(),
        "documents_missing_file": documents.filter(file_exists=False).count(),
        "documents_served": served.count(),
        "documents_served_today": served.filter(created_at__date=today).count(),
        "access_errors": errors.count(),
        "access_errors_today": errors.filter(created_at__date=today).count(),
        "access_logs_total": access_logs.count(),
        "integrity_failures": integrity_logs.count(),
        "integrity_failures_today": integrity_logs.filter(created_at__date=today).count(),
        "integrity_by_issue": list(
            integrity_logs.values("issue_type")
            .annotate(count=Count("id"))
            .order_by("-count")[:5]
        ),
        "recent_access_logs": list(
            access_logs.select_related("document").order_by("-created_at")[:8]
        ),
        "recent_integrity_logs": list(
            integrity_logs.select_related("document").order_by("-created_at")[:8]
        ),
    }


def manage_hub(request):
    return render(
        request,
        "issuer/manage/dashboard.html",
        {"stats": _get_dashboard_stats()},
    )


# --- Documents ---


def _document_file_available(doc: Document) -> bool:
    return find_readable_path(doc) is not None


def document_list(request):
    filters = get_filter_params(request, DOCUMENT_FILTER_FIELDS)
    qs = filter_documents(params=filters)
    choices = document_filter_choices()
    query = build_filter_query(filters)
    return render(
        request,
        "issuer/manage/document_list.html",
        {
            "page_obj": _paginate(request, qs),
            "filters": filters,
            "filter_query": query,
            "clear_url": reverse("issuer:document-list"),
            "document_types": choices["document_types"],
        },
    )


def document_detail(request, pk):
    obj = get_object_or_404(Document, pk=pk)
    can_view_file = _document_file_available(obj)
    return render(
        request,
        "issuer/manage/document_detail.html",
        {
            "object": obj,
            "can_view_file": can_view_file,
            "file_view_url": reverse("issuer:document-view-file", kwargs={"pk": pk})
            if can_view_file
            else "",
        },
    )


@require_http_methods(["GET"])
def document_view_file(request, pk):
    """Serve the stored document file for in-browser preview (manage UI only)."""
    doc = get_object_or_404(Document, pk=pk)
    full_path = find_readable_path(doc)
    if not full_path:
        return render(
            request,
            "issuer/manage/document_file_unavailable.html",
            {
                "object": doc,
                "expected_path": resolve_path(doc),
                "file_debug": diagnose_document_file(doc),
            },
            status=404,
        )
    with open(full_path, "rb") as f:
        content = f.read()

    content_type, _ = mimetypes.guess_type(full_path)
    if not content_type:
        content_type = "application/pdf"
    filename = os.path.basename(effective_file_name(doc.file_name)) or f"document-{doc.pk}.pdf"
    response = HttpResponse(content, content_type=content_type)
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response


def document_export(request):
    filters = get_filter_params(request, DOCUMENT_FILTER_FIELDS)
    qs = filter_documents(params=filters)
    fieldnames = [f.name for f in Document._meta.fields]
    rows = [{f.name: getattr(obj, f.name) for f in Document._meta.fields} for obj in qs]
    return _export_csv("digilocker_documents.csv", fieldnames, rows)


# --- Access logs ---


def accesslog_list(request):
    filters = get_filter_params(request, ACCESSLOG_FILTER_FIELDS)
    qs = filter_access_logs(params=filters).select_related("document")
    choices = accesslog_filter_choices()
    query = build_filter_query(filters)
    export_url = reverse("issuer:accesslog-export")
    if query:
        export_url = f"{export_url}?{query}"
    return render(
        request,
        "issuer/manage/accesslog_list.html",
        {
            "page_obj": _paginate(request, qs),
            "filters": filters,
            "filter_query": query,
            "export_url": export_url,
            "clear_url": reverse("issuer:accesslog-list"),
            "document_types": choices["document_types"],
        },
    )


def accesslog_detail(request, pk):
    obj = get_object_or_404(AccessLog.objects.select_related("document"), pk=pk)
    return render(request, "issuer/manage/accesslog_detail.html", {"object": obj})


def accesslog_export(request):
    filters = get_filter_params(request, ACCESSLOG_FILTER_FIELDS)
    qs = filter_access_logs(params=filters)
    fieldnames = [f.name for f in AccessLog._meta.fields]
    rows = [{f.name: getattr(obj, f.name) for f in AccessLog._meta.fields} for obj in qs]
    return _export_csv("access_logs.csv", fieldnames, rows)


# --- Integrity logs ---


def integritylog_list(request):
    filters = get_filter_params(request, INTEGRITYLOG_FILTER_FIELDS)
    qs = filter_integrity_logs(params=filters).select_related("document")
    choices = integritylog_filter_choices()
    query = build_filter_query(filters)
    export_url = reverse("issuer:integritylog-export")
    if query:
        export_url = f"{export_url}?{query}"
    return render(
        request,
        "issuer/manage/integritylog_list.html",
        {
            "page_obj": _paginate(request, qs),
            "filters": filters,
            "filter_query": query,
            "export_url": export_url,
            "clear_url": reverse("issuer:integritylog-list"),
            "issue_types": choices["issue_types"],
            "actions": choices["actions"],
            "document_types": choices["document_types"],
        },
    )


def integritylog_detail(request, pk):
    obj = get_object_or_404(IntegrityLog.objects.select_related("document"), pk=pk)
    return render(request, "issuer/manage/integritylog_detail.html", {"object": obj})


def integritylog_export(request):
    filters = get_filter_params(request, INTEGRITYLOG_FILTER_FIELDS)
    qs = filter_integrity_logs(params=filters)
    fieldnames = [f.name for f in IntegrityLog._meta.fields]
    rows = [{f.name: getattr(obj, f.name) for f in IntegrityLog._meta.fields} for obj in qs]
    return _export_csv("integrity_logs.csv", fieldnames, rows)


# --- KPI report ---


def kpi_report(request):
    default_from, default_to = previous_month_range()
    date_from_str = request.GET.get("date_from", "")
    date_to_str = request.GET.get("date_to", "")
    date_from, date_to, error = parse_period(date_from_str, date_to_str)

    report = build_kpi_report(date_from, date_to) if not error else None

    download_query = ""
    if date_from and date_to and not error:
        from urllib.parse import urlencode

        download_query = urlencode(
            {"date_from": date_from.isoformat(), "date_to": date_to.isoformat()}
        )

    return render(
        request,
        "issuer/manage/kpi_report.html",
        {
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "default_from": default_from.isoformat(),
            "default_to": default_to.isoformat(),
            "min_date": KPI_MIN_DATE.isoformat(),
            "error": error,
            "report": report,
            "kpi_catalog": kpi_definitions(),
            "download_url": (
                reverse("issuer:kpi-report-download") + f"?{download_query}"
                if download_query
                else ""
            ),
        },
    )


@require_http_methods(["GET"])
def kpi_report_download(request):
    date_from, date_to, error = parse_period(
        request.GET.get("date_from", ""),
        request.GET.get("date_to", ""),
    )
    if error:
        return HttpResponse(error, status=400)

    report = build_kpi_report(date_from, date_to)
    csv_body = export_kpi_csv(report)
    filename = f"kpi_report_{date_from}_{date_to}.csv"
    response = HttpResponse(csv_body, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


# --- Base64 PDF decoder (manage tools) ---

_DECODE_PDF_SESSION_PREFIX = "manage_decode_pdf:"
_DECODE_PDF_TTL_SECONDS = 900


def _decode_pdf_max_bytes() -> int:
    return int(getattr(settings, "DIGILOCKER_MAX_FILE_SIZE_MB", 10)) * 1024 * 1024


def _decode_pdf_session_key(token: str) -> str:
    return f"{_DECODE_PDF_SESSION_PREFIX}{token}"


def _prune_decode_pdf_sessions(request) -> None:
    """Drop expired decode-pdf entries from the session."""
    now = timezone.now()
    keys_to_delete = []
    for key, value in request.session.items():
        if not key.startswith(_DECODE_PDF_SESSION_PREFIX) or not isinstance(value, dict):
            continue
        created_raw = value.get("created")
        if not created_raw:
            keys_to_delete.append(key)
            continue
        try:
            created = datetime.fromisoformat(created_raw)
            if timezone.is_naive(created):
                created = timezone.make_aware(created)
        except (TypeError, ValueError):
            keys_to_delete.append(key)
            continue
        if (now - created).total_seconds() > _DECODE_PDF_TTL_SECONDS:
            keys_to_delete.append(key)
    for key in keys_to_delete:
        request.session.pop(key, None)


@require_http_methods(["GET", "POST"])
def decode_pdf_tool(request):
    """Paste Base64 DocContent, decode, and open the PDF in the browser."""
    _prune_decode_pdf_sessions(request)
    context = {
        "base64_input": "",
        "error": "",
        "view_url": "",
        "decoded_size": None,
    }

    if request.method == "POST":
        raw = request.POST.get("base64_input", "")
        context["base64_input"] = raw
        try:
            pdf_bytes = decode_pdf_bytes(raw, max_bytes=_decode_pdf_max_bytes())
        except ValueError as exc:
            context["error"] = str(exc)
        else:
            token = secrets.token_urlsafe(16)
            request.session[_decode_pdf_session_key(token)] = {
                "content_b64": base64.b64encode(pdf_bytes).decode("ascii"),
                "created": timezone.now().isoformat(),
            }
            request.session.modified = True
            context["view_url"] = reverse("issuer:decode-pdf-view", kwargs={"token": token})
            context["decoded_size"] = len(pdf_bytes)
            context["base64_input"] = ""

    return render(request, "issuer/manage/decode_pdf.html", context)


@require_http_methods(["GET"])
def decode_pdf_view(request, token):
    """Serve a decoded PDF stored temporarily in the session."""
    _prune_decode_pdf_sessions(request)
    entry = request.session.get(_decode_pdf_session_key(token))
    if not entry or "content_b64" not in entry:
        raise Http404("Decoded PDF not found or expired. Decode again from the tool page.")

    try:
        pdf_bytes = base64.b64decode(entry["content_b64"])
    except (ValueError, TypeError) as exc:
        raise Http404("Decoded PDF is corrupted.") from exc

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = 'inline; filename="decoded.pdf"'
    return response


# Require login + issuer.access_manage_portal on all management console views.
from issuer.manage_auth import require_manage_portal  # noqa: E402

_MANAGE_PORTAL_VIEWS = (
    "manage_hub",
    "document_list",
    "document_detail",
    "document_view_file",
    "document_export",
    "accesslog_list",
    "accesslog_detail",
    "accesslog_export",
    "integritylog_list",
    "integritylog_detail",
    "integritylog_export",
    "kpi_report",
    "kpi_report_download",
    "decode_pdf_tool",
    "decode_pdf_view",
)

for _manage_view_name in _MANAGE_PORTAL_VIEWS:
    globals()[_manage_view_name] = require_manage_portal(globals()[_manage_view_name])
