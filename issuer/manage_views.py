"""CRUD management UI for Document, AccessLog, and IntegrityLog."""

import csv
import mimetypes
import os
from io import StringIO

from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from issuer.forms import AccessLogForm, DocumentForm, IntegrityLogForm
from issuer.models import AccessLog, Document, IntegrityLog
from issuer.services.file_service import resolve_path

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
    if not (doc.file_name or "").strip():
        return False
    return os.path.isfile(resolve_path(doc))


def document_list(request):
    q = request.GET.get("q", "").strip()
    qs = Document.objects.all().order_by("-created_at")
    if q:
        qs = qs.filter(
            Q(authorization_number__icontains=q)
            | Q(document_type__icontains=q)
            | Q(employee_name__icontains=q)
            | Q(digilocker_uri__icontains=q)
            | Q(external_system_id__icontains=q)
        )
    return render(
        request,
        "issuer/manage/document_list.html",
        {
            "page_obj": _paginate(request, qs),
            "q": q,
            "export_url": reverse("issuer:document-export") + (f"?q={q}" if q else ""),
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
    if not _document_file_available(doc):
        return render(
            request,
            "issuer/manage/document_file_unavailable.html",
            {"object": doc, "expected_path": resolve_path(doc)},
            status=404,
        )

    full_path = resolve_path(doc)
    with open(full_path, "rb") as f:
        content = f.read()

    content_type, _ = mimetypes.guess_type(full_path)
    if not content_type:
        content_type = "application/pdf"
    filename = os.path.basename(doc.file_name) or f"document-{doc.pk}.pdf"
    response = HttpResponse(content, content_type=content_type)
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response


@require_http_methods(["GET", "POST"])
def document_create(request):
    if request.method == "POST":
        form = DocumentForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("issuer:document-list")
    else:
        form = DocumentForm()
    return render(
        request,
        "issuer/manage/form.html",
        {
            "form": form,
            "title": "Create Document",
            "cancel_url": reverse("issuer:document-list"),
        },
    )


@require_http_methods(["GET", "POST"])
def document_update(request, pk):
    obj = get_object_or_404(Document, pk=pk)
    if request.method == "POST":
        form = DocumentForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            return redirect("issuer:document-detail", pk=pk)
    else:
        form = DocumentForm(instance=obj)
    return render(
        request,
        "issuer/manage/form.html",
        {
            "form": form,
            "title": f"Edit Document #{pk}",
            "cancel_url": reverse("issuer:document-detail", pk=pk),
        },
    )


@require_http_methods(["GET", "POST"])
def document_delete(request, pk):
    obj = get_object_or_404(Document, pk=pk)
    if request.method == "POST":
        obj.delete()
        return redirect("issuer:document-list")
    return render(
        request,
        "issuer/manage/confirm_delete.html",
        {
            "object": obj,
            "object_label": str(obj),
            "cancel_url": reverse("issuer:document-detail", pk=pk),
        },
    )


def document_export(request):
    q = request.GET.get("q", "").strip()
    qs = Document.objects.all().order_by("-created_at")
    if q:
        qs = qs.filter(
            Q(authorization_number__icontains=q)
            | Q(document_type__icontains=q)
            | Q(employee_name__icontains=q)
            | Q(digilocker_uri__icontains=q)
            | Q(external_system_id__icontains=q)
        )
    fieldnames = [f.name for f in Document._meta.fields]
    rows = [{f.name: getattr(obj, f.name) for f in Document._meta.fields} for obj in qs]
    return _export_csv("digilocker_documents.csv", fieldnames, rows)


# --- Access logs ---


def accesslog_list(request):
    q = request.GET.get("q", "").strip()
    qs = AccessLog.objects.select_related("document").all().order_by("-created_at")
    if q:
        qs = qs.filter(
            Q(txn_id__icontains=q)
            | Q(authorization_number__icontains=q)
            | Q(digilocker_id__icontains=q)
            | Q(requested_mobile__icontains=q)
        )
    return render(
        request,
        "issuer/manage/accesslog_list.html",
        {
            "page_obj": _paginate(request, qs),
            "q": q,
            "export_url": reverse("issuer:accesslog-export") + (f"?q={q}" if q else ""),
        },
    )


def accesslog_detail(request, pk):
    obj = get_object_or_404(AccessLog.objects.select_related("document"), pk=pk)
    return render(request, "issuer/manage/accesslog_detail.html", {"object": obj})


@require_http_methods(["GET", "POST"])
def accesslog_create(request):
    if request.method == "POST":
        form = AccessLogForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("issuer:accesslog-list")
    else:
        form = AccessLogForm()
    return render(
        request,
        "issuer/manage/form.html",
        {
            "form": form,
            "title": "Create Access Log",
            "cancel_url": reverse("issuer:accesslog-list"),
        },
    )


@require_http_methods(["GET", "POST"])
def accesslog_update(request, pk):
    obj = get_object_or_404(AccessLog, pk=pk)
    if request.method == "POST":
        form = AccessLogForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            return redirect("issuer:accesslog-detail", pk=pk)
    else:
        form = AccessLogForm(instance=obj)
    return render(
        request,
        "issuer/manage/form.html",
        {
            "form": form,
            "title": f"Edit Access Log #{pk}",
            "cancel_url": reverse("issuer:accesslog-detail", pk=pk),
        },
    )


@require_http_methods(["GET", "POST"])
def accesslog_delete(request, pk):
    obj = get_object_or_404(AccessLog, pk=pk)
    if request.method == "POST":
        obj.delete()
        return redirect("issuer:accesslog-list")
    return render(
        request,
        "issuer/manage/confirm_delete.html",
        {
            "object": obj,
            "object_label": str(obj),
            "cancel_url": reverse("issuer:accesslog-detail", pk=pk),
        },
    )


def accesslog_export(request):
    q = request.GET.get("q", "").strip()
    qs = AccessLog.objects.all().order_by("-created_at")
    if q:
        qs = qs.filter(
            Q(txn_id__icontains=q)
            | Q(authorization_number__icontains=q)
            | Q(digilocker_id__icontains=q)
            | Q(requested_mobile__icontains=q)
        )
    fieldnames = [f.name for f in AccessLog._meta.fields]
    rows = [{f.name: getattr(obj, f.name) for f in AccessLog._meta.fields} for obj in qs]
    return _export_csv("access_logs.csv", fieldnames, rows)


# --- Integrity logs ---


def integritylog_list(request):
    q = request.GET.get("q", "").strip()
    qs = IntegrityLog.objects.select_related("document").all().order_by("-created_at")
    if q:
        qs = qs.filter(
            Q(issue_type__icontains=q)
            | Q(authorization_number__icontains=q)
            | Q(digilocker_txn__icontains=q)
            | Q(digilocker_id__icontains=q)
        )
    return render(
        request,
        "issuer/manage/integritylog_list.html",
        {
            "page_obj": _paginate(request, qs),
            "q": q,
            "export_url": reverse("issuer:integritylog-export") + (f"?q={q}" if q else ""),
        },
    )


def integritylog_detail(request, pk):
    obj = get_object_or_404(IntegrityLog.objects.select_related("document"), pk=pk)
    return render(request, "issuer/manage/integritylog_detail.html", {"object": obj})


@require_http_methods(["GET", "POST"])
def integritylog_create(request):
    if request.method == "POST":
        form = IntegrityLogForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("issuer:integritylog-list")
    else:
        form = IntegrityLogForm()
    return render(
        request,
        "issuer/manage/form.html",
        {
            "form": form,
            "title": "Create Integrity Log",
            "cancel_url": reverse("issuer:integritylog-list"),
        },
    )


@require_http_methods(["GET", "POST"])
def integritylog_update(request, pk):
    obj = get_object_or_404(IntegrityLog, pk=pk)
    if request.method == "POST":
        form = IntegrityLogForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            return redirect("issuer:integritylog-detail", pk=pk)
    else:
        form = IntegrityLogForm(instance=obj)
    return render(
        request,
        "issuer/manage/form.html",
        {
            "form": form,
            "title": f"Edit Integrity Log #{pk}",
            "cancel_url": reverse("issuer:integritylog-detail", pk=pk),
        },
    )


@require_http_methods(["GET", "POST"])
def integritylog_delete(request, pk):
    obj = get_object_or_404(IntegrityLog, pk=pk)
    if request.method == "POST":
        obj.delete()
        return redirect("issuer:integritylog-list")
    return render(
        request,
        "issuer/manage/confirm_delete.html",
        {
            "object": obj,
            "object_label": str(obj),
            "cancel_url": reverse("issuer:integritylog-detail", pk=pk),
        },
    )


def integritylog_export(request):
    q = request.GET.get("q", "").strip()
    qs = IntegrityLog.objects.all().order_by("-created_at")
    if q:
        qs = qs.filter(
            Q(issue_type__icontains=q)
            | Q(authorization_number__icontains=q)
            | Q(digilocker_txn__icontains=q)
            | Q(digilocker_id__icontains=q)
        )
    fieldnames = [f.name for f in IntegrityLog._meta.fields]
    rows = [{f.name: getattr(obj, f.name) for f in IntegrityLog._meta.fields} for obj in qs]
    return _export_csv("integrity_logs.csv", fieldnames, rows)
