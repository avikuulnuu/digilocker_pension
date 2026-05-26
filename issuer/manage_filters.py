"""Query filtering helpers for the management portal list/export views."""

from datetime import datetime
from urllib.parse import urlencode

from django.db.models import Q, QuerySet

from issuer.models import AccessLog, Document, IntegrityLog

BOOL_CHOICES = ("", "yes", "no")


def get_filter_params(request, field_names: list[str]) -> dict[str, str]:
    """Read known GET filter fields from the request."""
    return {name: (request.GET.get(name) or "").strip() for name in field_names}


def build_filter_query(params: dict[str, str], *, page: str | int | None = None) -> str:
    """Build a query string preserving active filters (and optional page)."""
    items = [(k, v) for k, v in params.items() if v]
    if page is not None:
        items.append(("page", str(page)))
    return urlencode(items)


def _apply_bool(qs: QuerySet, field: str, value: str) -> QuerySet:
    if value == "yes":
        return qs.filter(**{field: True})
    if value == "no":
        return qs.filter(**{field: False})
    return qs


def _apply_date_from(qs: QuerySet, field: str, value: str) -> QuerySet:
    if not value:
        return qs
    try:
        day = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return qs
    return qs.filter(**{f"{field}__date__gte": day})


def _apply_date_to(qs: QuerySet, field: str, value: str) -> QuerySet:
    if not value:
        return qs
    try:
        day = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return qs
    return qs.filter(**{f"{field}__date__lte": day})


def _apply_icontains(qs: QuerySet, field: str, value: str) -> QuerySet:
    if value:
        return qs.filter(**{f"{field}__icontains": value})
    return qs


def _apply_exact(qs: QuerySet, field: str, value: str) -> QuerySet:
    if value:
        return qs.filter(**{field: value})
    return qs


DOCUMENT_FILTER_FIELDS = [
    "q",
    "authorization_number",
    "document_type",
    "employee_name",
    "employee_mobile",
    "file_name",
    "external_system_id",
    "digilocker_uri",
    "is_active",
    "digilocker_enabled",
    "file_exists",
    "created_from",
    "created_to",
]


def filter_documents(qs: QuerySet | None = None, params: dict[str, str] | None = None) -> QuerySet:
    qs = qs or Document.objects.all()
    params = params or {}

    q = params.get("q", "")
    if q:
        qs = qs.filter(
            Q(authorization_number__icontains=q)
            | Q(document_type__icontains=q)
            | Q(employee_name__icontains=q)
            | Q(digilocker_uri__icontains=q)
            | Q(external_system_id__icontains=q)
            | Q(file_name__icontains=q)
        )

    qs = _apply_icontains(qs, "authorization_number", params.get("authorization_number", ""))
    qs = _apply_exact(qs, "document_type", params.get("document_type", ""))
    qs = _apply_icontains(qs, "employee_name", params.get("employee_name", ""))
    qs = _apply_icontains(qs, "employee_mobile", params.get("employee_mobile", ""))
    qs = _apply_icontains(qs, "file_name", params.get("file_name", ""))
    qs = _apply_icontains(qs, "external_system_id", params.get("external_system_id", ""))
    qs = _apply_icontains(qs, "digilocker_uri", params.get("digilocker_uri", ""))
    qs = _apply_bool(qs, "is_active", params.get("is_active", ""))
    qs = _apply_bool(qs, "digilocker_enabled", params.get("digilocker_enabled", ""))
    qs = _apply_bool(qs, "file_exists", params.get("file_exists", ""))
    qs = _apply_date_from(qs, "created_at", params.get("created_from", ""))
    qs = _apply_date_to(qs, "created_at", params.get("created_to", ""))
    return qs.order_by("-created_at")


def document_filter_choices() -> dict:
    return {
        "document_types": list(
            Document.objects.order_by("document_type")
            .values_list("document_type", flat=True)
            .distinct()
        ),
    }


ACCESSLOG_FILTER_FIELDS = [
    "q",
    "txn_id",
    "authorization_number",
    "document_type",
    "digilocker_id",
    "request_ip",
    "requested_mobile",
    "response_status",
    "has_error",
    "created_from",
    "created_to",
]


def filter_access_logs(qs: QuerySet | None = None, params: dict[str, str] | None = None) -> QuerySet:
    qs = qs or AccessLog.objects.all()
    params = params or {}

    q = params.get("q", "")
    if q:
        qs = qs.filter(
            Q(txn_id__icontains=q)
            | Q(authorization_number__icontains=q)
            | Q(digilocker_id__icontains=q)
            | Q(requested_mobile__icontains=q)
            | Q(error_message__icontains=q)
        )

    qs = _apply_icontains(qs, "txn_id", params.get("txn_id", ""))
    qs = _apply_icontains(qs, "authorization_number", params.get("authorization_number", ""))
    qs = _apply_exact(qs, "document_type", params.get("document_type", ""))
    qs = _apply_icontains(qs, "digilocker_id", params.get("digilocker_id", ""))
    qs = _apply_icontains(qs, "request_ip", params.get("request_ip", ""))
    qs = _apply_icontains(qs, "requested_mobile", params.get("requested_mobile", ""))

    status = params.get("response_status", "")
    if status == "success":
        qs = qs.filter(response_status=1)
    elif status == "error":
        qs = qs.exclude(response_status=1)

    has_error = params.get("has_error", "")
    if has_error == "yes":
        qs = qs.exclude(error_message="")
    elif has_error == "no":
        qs = qs.filter(error_message="")

    qs = _apply_date_from(qs, "created_at", params.get("created_from", ""))
    qs = _apply_date_to(qs, "created_at", params.get("created_to", ""))
    return qs.order_by("-created_at")


def accesslog_filter_choices() -> dict:
    return {
        "document_types": list(
            AccessLog.objects.exclude(document_type="")
            .order_by("document_type")
            .values_list("document_type", flat=True)
            .distinct()
        ),
    }


INTEGRITYLOG_FILTER_FIELDS = [
    "q",
    "issue_type",
    "action_taken",
    "authorization_number",
    "document_type",
    "document_id",
    "digilocker_txn",
    "request_ip",
    "created_from",
    "created_to",
]


def filter_integrity_logs(qs: QuerySet | None = None, params: dict[str, str] | None = None) -> QuerySet:
    qs = qs or IntegrityLog.objects.all()
    params = params or {}

    q = params.get("q", "")
    if q:
        qs = qs.filter(
            Q(issue_type__icontains=q)
            | Q(authorization_number__icontains=q)
            | Q(digilocker_txn__icontains=q)
            | Q(digilocker_id__icontains=q)
            | Q(file_path__icontains=q)
        )

    qs = _apply_exact(qs, "issue_type", params.get("issue_type", ""))
    qs = _apply_exact(qs, "action_taken", params.get("action_taken", ""))
    qs = _apply_icontains(qs, "authorization_number", params.get("authorization_number", ""))
    qs = _apply_exact(qs, "document_type", params.get("document_type", ""))
    qs = _apply_icontains(qs, "request_ip", params.get("request_ip", ""))
    qs = _apply_icontains(qs, "digilocker_txn", params.get("digilocker_txn", ""))

    doc_id = params.get("document_id", "")
    if doc_id.isdigit():
        qs = qs.filter(document_id=int(doc_id))

    qs = _apply_date_from(qs, "created_at", params.get("created_from", ""))
    qs = _apply_date_to(qs, "created_at", params.get("created_to", ""))
    return qs.order_by("-created_at")


def integritylog_filter_choices() -> dict:
    return {
        "issue_types": list(
            IntegrityLog.objects.order_by("issue_type")
            .values_list("issue_type", flat=True)
            .distinct()
        ),
        "actions": list(
            IntegrityLog.objects.exclude(action_taken="")
            .order_by("action_taken")
            .values_list("action_taken", flat=True)
            .distinct()
        ),
        "document_types": list(
            IntegrityLog.objects.exclude(document_type="")
            .order_by("document_type")
            .values_list("document_type", flat=True)
            .distinct()
        ),
    }
