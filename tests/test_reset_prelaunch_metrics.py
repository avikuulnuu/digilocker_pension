from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from issuer.models import AccessLog, Document, IntegrityLog


class ResetPrelaunchMetricsCommandTest(TestCase):
    def setUp(self):
        self.document = Document.objects.create(
            authorization_number="AUTH-RESET",
            document_type="PECER",
            external_system_id="RESET-1",
            authorization_date=timezone.localdate(),
            employee_name="Test User",
            file_name="test-document",
            access_count=3,
            last_accessed_at=timezone.now(),
        )
        AccessLog.objects.create(document=self.document, response_status=1)
        IntegrityLog.objects.create(
            document=self.document,
            issue_type="CHECKSUM_MISMATCH",
        )

    def test_preview_does_not_change_data(self):
        output = StringIO()

        call_command("reset_prelaunch_metrics", stdout=output)

        self.assertEqual(AccessLog.objects.count(), 1)
        self.assertEqual(IntegrityLog.objects.count(), 1)
        self.assertIn("Preview only", output.getvalue())

    def test_invalid_confirmation_does_not_change_data(self):
        with self.assertRaises(CommandError):
            call_command("reset_prelaunch_metrics", confirm="WRONG")

        self.assertEqual(AccessLog.objects.count(), 1)

    def test_confirmation_clears_metrics_and_preserves_document(self):
        call_command(
            "reset_prelaunch_metrics",
            confirm="RESET-PRELAUNCH-METRICS",
        )

        self.assertFalse(AccessLog.objects.exists())
        self.assertFalse(IntegrityLog.objects.exists())
        self.document.refresh_from_db()
        self.assertEqual(self.document.access_count, 0)
        self.assertIsNone(self.document.last_accessed_at)