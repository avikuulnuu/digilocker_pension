"""Tests for manage portal document file preview."""

import os
import tempfile
from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from issuer.models import Document
from tests.test_manage_auth import grant_manage_portal

User = get_user_model()


@override_settings(CAPTCHA_TEST_MODE=True)
class DocumentFilePreviewTest(TestCase):
    def setUp(self):
        self.base_path = tempfile.mkdtemp()
        self.user = User.objects.create_user(username="ops", password="test-pass-123")
        grant_manage_portal(self.user)
        self.client.force_login(self.user)

        self.doc = Document.objects.create(
            authorization_number="AUTH100",
            document_type="GPFFP",
            external_system_id="34420",
            authorization_date=date(2024, 1, 1),
            employee_name="Test User",
            file_name="34420",
            is_active=False,
            file_exists=False,
        )
        self.file_url = reverse("issuer:document-view-file", kwargs={"pk": self.doc.pk})
        self._base_path_patcher = patch.object(
            __import__("django.conf", fromlist=["settings"]).settings,
            "DIGILOCKER_GPF_STORAGE_PATH",
            self.base_path,
        )
        self._base_path_patcher.start()

    def tearDown(self):
        self._base_path_patcher.stop()
        if os.path.exists(self.base_path):
            os.rmdir(self.base_path)

    def test_inactive_missing_file_skips_disk_lookup(self):
        with patch("issuer.manage_views.find_readable_path") as find_path:
            response = self.client.get(self.file_url)
        find_path.assert_not_called()
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "File does not exist", status_code=404)
        self.assertContains(response, "34420.pdf", status_code=404)
        self.assertNotContains(response, "Path diagnostics", status_code=404)

    def test_detail_page_hides_view_link_when_preview_blocked(self):
        response = self.client.get(
            reverse("issuer:document-detail", kwargs={"pk": self.doc.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "View document")
