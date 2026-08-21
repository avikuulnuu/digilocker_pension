"""KPI metrics for the management portal report."""

from datetime import date, datetime, time
from io import StringIO

import csv

from django.db.models import Avg, Count, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone

from issuer.models import AccessLog, Document, IntegrityLog

MAX_KPI_RANGE_DAYS = 730  # ~2 years
KPI_MIN_DATE = date(2026, 1, 1)
DOCUMENT_COHORT_MIN_DATE = date(2026, 7, 1)


def _clamp_to_min_date(date_from: date, date_to: date) -> tuple[date, date]:
    if date_from < KPI_MIN_DATE:
        date_from = KPI_MIN_DATE
    if date_to < KPI_MIN_DATE:
        date_to = KPI_MIN_DATE
    if date_from > date_to:
        date_to = date_from
    return date_from, date_to


def default_report_range(today: date | None = None) -> tuple[date, date]:
    """Available KPI history from January 2026 through today."""
    today = today or timezone.localdate()
    return _clamp_to_min_date(KPI_MIN_DATE, today)


def parse_period(date_from_str: str, date_to_str: str) -> tuple[date, date, str | None]:
    """Parse and validate a date range. Returns (from, to, error_message)."""
    default_from, default_to = default_report_range()
    if not date_from_str:
        date_from = default_from
    else:
        try:
            date_from = datetime.strptime(date_from_str, "%Y-%m-%d").date()
        except ValueError:
            return default_from, default_to, "Invalid start date."

    if not date_to_str:
        date_to = default_to
    else:
        try:
            date_to = datetime.strptime(date_to_str, "%Y-%m-%d").date()
        except ValueError:
            return default_from, default_to, "Invalid end date."

    if date_from < KPI_MIN_DATE or date_to < KPI_MIN_DATE:
        return date_from, date_to, "Dates before 2026-01-01 are not available."

    if date_from > date_to:
        return date_from, date_to, "Start date must be on or before end date."

    if (date_to - date_from).days > MAX_KPI_RANGE_DAYS:
        return (
            date_from,
            date_to,
            f"Date range cannot exceed {MAX_KPI_RANGE_DAYS} days.",
        )
    return date_from, date_to, None


def _period_bounds(date_from: date, date_to: date) -> tuple[datetime, datetime]:
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(date_from, time.min), tz)
    end = timezone.make_aware(datetime.combine(date_to, time.max), tz)
    return start, end


def _pct(part: int, whole: int) -> str:
    if whole == 0:
        return "0.0"
    return f"{(part / whole) * 100:.1f}"


EMPTY_VALUE = "n/a"


def _display_text(value) -> str:
    """Normalize text for HTML/CSV (avoid mojibake in Excel)."""
    if value is None:
        return ""
    return (
        str(value)
        .replace("\u2014", "-")
        .replace("\u2013", "-")
        .replace("\u2260", "!=")
        .replace("\u2018", "'")
        .replace("\u2019", "'")
    )


HIGHLIGHT_METRICS = {
    "Total document records",
    "Logged Pull URI attempts",
    "Documents served",
    "Operational success rate (%)",
    "Service failures",
    "Total integrity events",
    "Document records added",
}


def _extract_highlights(summary_rows: list[tuple]) -> list[dict]:
    highlights = []
    for section, metric, value, _notes in summary_rows:
        if metric in HIGHLIGHT_METRICS:
            highlights.append(
                {
                    "label": metric,
                    "value": value,
                    "section": section,
                    "variant": (
                        "danger"
                        if metric in ("Service failures", "Total integrity events")
                        and str(value) not in ("0", "0.0", EMPTY_VALUE, "n/a")
                        else "success"
                        if metric in ("Operational success rate (%)", "Documents served")
                        else "info"
                    ),
                }
            )
    return highlights


def access_outcome_counts(access_logs) -> dict:
    """Aggregate protocol and operational outcomes for an AccessLog queryset."""
    counts = access_logs.aggregate(
        total=Count("id"),
        documents_served=Count("id", filter=Q(response_status=1)),
        handled=Count(
            "id",
            filter=Q(outcome_class=AccessLog.OutcomeClass.HANDLED),
        ),
        service_failures=Count(
            "id",
            filter=Q(outcome_class=AccessLog.OutcomeClass.SERVICE_FAILURE),
        ),
        rejected=Count(
            "id",
            filter=Q(outcome_class=AccessLog.OutcomeClass.REJECTED),
        ),
        pending=Count(
            "id",
            filter=Q(outcome_class=AccessLog.OutcomeClass.PENDING),
        ),
        unclassified=Count(
            "id",
            filter=Q(
                outcome_class=AccessLog.OutcomeClass.LEGACY_UNCLASSIFIED
            ),
        ),
    )
    operational_total = counts["handled"] + counts["service_failures"]
    counts["operational_success_rate"] = _pct(
        counts["handled"],
        operational_total,
    )
    return counts


def build_kpi_report(date_from: date, date_to: date) -> dict:
    """Compute KPI sections for the given inclusive date range."""
    start, end = _period_bounds(date_from, date_to)
    generated_at = timezone.now()

    access_in_period = AccessLog.objects.filter(created_at__gte=start, created_at__lte=end)
    integrity_in_period = IntegrityLog.objects.filter(created_at__gte=start, created_at__lte=end)
    docs_created_in_period = Document.objects.filter(
        created_at__gte=start, created_at__lte=end
    )
    cohort_from = max(date_from, DOCUMENT_COHORT_MIN_DATE)
    document_additions_by_month = []
    if cohort_from <= date_to:
        cohort_start, _ = _period_bounds(cohort_from, date_to)
        document_additions_by_month = list(
            Document.objects.filter(
                created_at__gte=cohort_start,
                created_at__lte=end,
            )
            .annotate(month=TruncMonth("created_at"))
            .values("month")
            .annotate(count=Count("id"))
            .order_by("month")
        )

    outcome_counts = access_outcome_counts(access_in_period)
    access_with_err_msg = access_in_period.exclude(error_message="").count()
    avg_ms_all = access_in_period.aggregate(v=Avg("processing_time_ms"))["v"]
    avg_ms_ok = access_in_period.filter(response_status=1).aggregate(
        v=Avg("processing_time_ms")
    )["v"]

    integrity_total = integrity_in_period.count()
    integrity_blocked = integrity_in_period.filter(action_taken="BLOCKED").count()
    integrity_served = integrity_in_period.filter(action_taken="SERVED").count()

    summary_rows = [
        ("Report", "Period", f"{date_from} to {date_to}", "Inclusive"),
        ("Report", "Generated at", generated_at.isoformat(), ""),
        ("", "", "", ""),
        ("Document registry (current inventory)", "Total document records", Document.objects.count(), "All time"),
        (
            "Document registry (current inventory)",
            "Active documents",
            Document.objects.filter(is_active=True).count(),
            "is_active=True",
        ),
        (
            "Documents (in period)",
            "Document records added",
            docs_created_in_period.count(),
            "records first inserted during the selected period",
        ),
        ("", "", "", ""),
        (
            "API access (in period)",
            "Logged Pull URI attempts",
            outcome_counts["total"],
            "POST requests recorded by the Pull URI view",
        ),
        (
            "API access (in period)",
            "Documents served",
            outcome_counts["documents_served"],
            "document-bearing responses (response_status=1)",
        ),
        (
            "API access (in period)",
            "Handled outcomes",
            outcome_counts["handled"],
            "expected business outcomes, including valid no-record responses",
        ),
        (
            "API access (in period)",
            "Service failures",
            outcome_counts["service_failures"],
            "file, integrity, disabled-access, or internal failures",
        ),
        (
            "API access (in period)",
            "Operational success rate (%)",
            outcome_counts["operational_success_rate"],
            "handled / (handled + service failures)",
        ),
        (
            "API access (in period)",
            "Rejected requests",
            outcome_counts["rejected"],
            "malformed, unauthenticated, or missing required identifier",
        ),
        (
            "API access (in period)",
            "Requests with error message",
            access_with_err_msg,
            "non-empty error_message",
        ),
        (
            "API access (in period)",
            "Unique authorization numbers",
            access_in_period.exclude(authorization_number="")
            .values("authorization_number")
            .distinct()
            .count(),
            "",
        ),
        (
            "API access (in period)",
            "Unique transaction IDs",
            access_in_period.exclude(txn_id="").values("txn_id").distinct().count(),
            "",
        ),
        (
            "API access (in period)",
            "Avg processing time (ms) - documents served",
            f"{avg_ms_ok:.1f}" if avg_ms_ok is not None else EMPTY_VALUE,
            "document-bearing responses only",
        ),
        (
            "API access (in period)",
            "Avg processing time (ms) - all",
            f"{avg_ms_all:.1f}" if avg_ms_all is not None else EMPTY_VALUE,
            "",
        ),
        ("", "", "", ""),
        (
            "Integrity (in period)",
            "Total integrity events",
            integrity_total,
            "integrity_logs in period",
        ),
        (
            "Integrity (in period)",
            "Blocked (STRICT)",
            integrity_blocked,
            "action_taken=BLOCKED",
        ),
        (
            "Integrity (in period)",
            "Served despite issue",
            integrity_served,
            "action_taken=SERVED",
        ),
    ]

    access_by_type = []
    for row in (
        access_in_period.values("document_type")
        .annotate(
            total=Count("id"),
            served=Count("id", filter=Q(response_status=1)),
            handled=Count(
                "id",
                filter=Q(outcome_class=AccessLog.OutcomeClass.HANDLED),
            ),
            service_failures=Count(
                "id",
                filter=Q(outcome_class=AccessLog.OutcomeClass.SERVICE_FAILURE),
            ),
            rejected=Count(
                "id",
                filter=Q(outcome_class=AccessLog.OutcomeClass.REJECTED),
            ),
        )
        .order_by("-total")
    ):
        access_by_type.append(row)

    integrity_by_issue = list(
        integrity_in_period.values("issue_type")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    integrity_by_action = list(
        integrity_in_period.exclude(action_taken="")
        .values("action_taken")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    summary_rows = [
        tuple(_display_text(cell) for cell in row) for row in summary_rows
    ]

    return {
        "date_from": date_from,
        "date_to": date_to,
        "documents_served": outcome_counts["documents_served"],
        "generated_at": generated_at,
        "summary_rows": summary_rows,
        "highlights": _extract_highlights(summary_rows),
        "access_by_type": access_by_type,
        "document_additions_by_month": document_additions_by_month,
        "integrity_by_issue": integrity_by_issue,
        "integrity_by_action": integrity_by_action,
    }


def kpi_definitions() -> list[dict]:
    """Human-readable KPI catalog shown on the report page."""
    return [
        {
            "category": "Document registry",
            "scope": "Current snapshot",
            "metrics": [
                "Total document records",
                "Active documents",
            ],
        },
        {
            "category": "Document onboarding",
            "scope": "Selected period",
            "metrics": [
                "Document records first inserted in period",
                "Monthly document records added from July 2026",
            ],
        },
        {
            "category": "API access (Pull URI)",
            "scope": "Selected period",
            "metrics": [
                "Logged Pull URI attempts",
                "Documents served (document-bearing responses)",
                "Handled outcomes vs service failures and operational success rate",
                "Rejected requests",
                "Requests with recorded error messages",
                "Unique authorization numbers and transaction IDs",
                "Average response processing time (ms)",
                "Breakdown by document type",
            ],
        },
        {
            "category": "File integrity",
            "scope": "Selected period",
            "metrics": [
                "Total integrity check failures logged",
                "Blocked vs served-with-warning counts",
                "Breakdown by issue type (e.g. FILE_MISSING, CHECKSUM_MISMATCH)",
                "Breakdown by action taken",
            ],
        },
    ]


def export_kpi_csv(report: dict) -> str:
    """Render KPI report as CSV text (UTF-8 with BOM for Excel)."""
    buffer = StringIO()
    buffer.write("\ufeff")
    writer = csv.writer(buffer)
    writer.writerow([_display_text("DigiLocker Issuer - KPI Report")])
    writer.writerow([])

    writer.writerow(["Summary metrics"])
    writer.writerow(["Section", "Metric", "Value", "Notes"])
    for row in report["summary_rows"]:
        writer.writerow([_display_text(cell) for cell in row])

    writer.writerow([])
    writer.writerow(["Document records added by month (from July 2026)"])
    writer.writerow(["Month", "Records added"])
    for row in report["document_additions_by_month"]:
        writer.writerow([row["month"].strftime("%B %Y"), row["count"]])

    writer.writerow([])
    writer.writerow(["Pull URI outcomes by document type (in period)"])
    writer.writerow(
        [
            "Document type",
            "Logged attempts",
            "Documents served",
            "Handled outcomes",
            "Service failures",
            "Rejected requests",
        ]
    )
    for row in report["access_by_type"]:
        doc_type = row["document_type"] or "(blank)"
        writer.writerow(
            [
                _display_text(doc_type),
                row["total"],
                row["served"],
                row["handled"],
                row["service_failures"],
                row["rejected"],
            ]
        )

    writer.writerow([])
    writer.writerow(["Integrity events by issue type (in period)"])
    writer.writerow(["Issue type", "Count"])
    for row in report["integrity_by_issue"]:
        writer.writerow([_display_text(row["issue_type"]), row["count"]])

    writer.writerow([])
    writer.writerow(["Integrity events by action (in period)"])
    writer.writerow(["Action taken", "Count"])
    for row in report["integrity_by_action"]:
        writer.writerow([_display_text(row["action_taken"]), row["count"]])

    return buffer.getvalue()
