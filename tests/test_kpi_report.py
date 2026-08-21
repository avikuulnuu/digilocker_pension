"""Tests for KPI report calculations and presentation."""

from datetime import date, datetime

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from issuer.kpi_report import build_kpi_report, default_report_range
from issuer.models import AccessLog, Document


User = get_user_model()


def _summary_metrics(report):
    return {
        metric: value
        for _section, metric, value, _notes in report["summary_rows"]
        if metric
    }


class KPIReportCalculationTest(TestCase):
    def test_default_report_range_runs_from_january_2026_through_today(self):
        self.assertEqual(
            default_report_range(date(2026, 8, 21)),
            (date(2026, 1, 1), date(2026, 8, 21)),
        )

    def _create_document(self, external_id):
        return Document.objects.create(
            authorization_number=f"AUTH{external_id}",
            document_type="PECER",
            external_system_id=str(external_id),
            authorization_date=date(2026, 1, 1),
            employee_name="Test User",
            file_name=f"document-{external_id}",
        )

    def test_operational_rate_excludes_rejected_and_unclassified_attempts(self):
        AccessLog.objects.create(
            document_type="PECER",
            response_status=1,
            outcome_class=AccessLog.OutcomeClass.HANDLED,
        )
        AccessLog.objects.create(
            document_type="PECER",
            response_status=0,
            outcome_class=AccessLog.OutcomeClass.HANDLED,
        )
        AccessLog.objects.create(
            document_type="PECER",
            response_status=0,
            outcome_class=AccessLog.OutcomeClass.SERVICE_FAILURE,
        )
        AccessLog.objects.create(
            response_status=0,
            outcome_class=AccessLog.OutcomeClass.REJECTED,
        )
        AccessLog.objects.create()

        report = build_kpi_report(date.today(), date.today())
        metrics = _summary_metrics(report)

        self.assertEqual(metrics["Logged Pull URI attempts"], "5")
        self.assertEqual(metrics["Documents served"], "1")
        self.assertEqual(metrics["Handled outcomes"], "2")
        self.assertEqual(metrics["Service failures"], "1")
        self.assertEqual(metrics["Rejected requests"], "1")
        self.assertEqual(metrics["Operational success rate (%)"], "66.7")

        pecer = next(
            row for row in report["access_by_type"]
            if row["document_type"] == "PECER"
        )
        self.assertEqual(pecer["served"], 1)
        self.assertEqual(pecer["handled"], 2)
        self.assertEqual(pecer["service_failures"], 1)

    def test_operational_rate_is_zero_without_classified_outcomes(self):
        AccessLog.objects.create()

        report = build_kpi_report(date.today(), date.today())

        self.assertEqual(
            _summary_metrics(report)["Operational success rate (%)"],
            "0.0",
        )

    def test_monthly_document_additions_begin_in_july_and_ignore_updates(self):
        tz = timezone.get_current_timezone()
        june_document = self._create_document(1)
        july_document = self._create_document(2)
        august_document = self._create_document(3)
        Document.objects.filter(pk=june_document.pk).update(
            created_at=timezone.make_aware(datetime(2026, 6, 15), tz)
        )
        Document.objects.filter(pk=july_document.pk).update(
            created_at=timezone.make_aware(datetime(2026, 7, 15), tz)
        )
        Document.objects.filter(pk=august_document.pk).update(
            created_at=timezone.make_aware(datetime(2026, 8, 15), tz)
        )

        july_document.employee_name = "Updated User"
        july_document.save(update_fields=["employee_name", "updated_at"])

        report = build_kpi_report(date(2026, 6, 1), date(2026, 8, 31))

        self.assertEqual(
            [
                (row["month"].date(), row["count"])
                for row in report["document_additions_by_month"]
            ],
            [(date(2026, 7, 1), 1), (date(2026, 8, 1), 1)],
        )


class KPIReportViewTest(TestCase):
    def setUp(self):
        user = User.objects.create_user(username="kpi_user", password="test-pass-123")
        permission = Permission.objects.get(
            codename="access_manage_portal",
            content_type=ContentType.objects.get_for_model(Document),
        )
        user.user_permissions.add(permission)
        self.client.force_login(user)

    def test_empty_period_states_zero_documents_served_with_readable_range(self):
        response = self.client.get(
            reverse("issuer:kpi-report"),
            {"date_from": "2026-07-01", "date_to": "2026-07-31"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "0 documents served")
        self.assertContains(response, "Reporting period")
        self.assertContains(response, "July 1, 2026 to July 31, 2026")
