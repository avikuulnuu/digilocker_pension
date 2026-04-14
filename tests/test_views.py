"""Integration tests for the Pull URI and Document Fetch views."""

import base64
import hashlib
import hmac as hmac_mod
import os
import tempfile
from datetime import date
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase
from django.utils import timezone

from issuer.models import AccessLog, Document


class PullURIViewTest(TestCase):
    def test_document_fetch_logs_extra_fields(self):
        # Set up extra fields on the document
        self.doc.employee_mobile = "9999999999"
        self.doc.file_checksum = "abc123"
        self.doc.save()

        # Fetch the document with a mobile param
        url = f"/issuer/document/{self.doc.uri}?mobile=8888888888"
        hmac_sig = "dummyhmac"  # bypassed in test
        with patch("issuer.views.read_file_bytes", return_value=b"PDFDATA"):
            with patch("issuer.views.Document.objects.get", return_value=self.doc):
                response = self.client.get(url, HTTP_X_DIGILOCKER_HMAC=hmac_sig)
        self.assertEqual(response.status_code, 200)
        log = AccessLog.objects.latest("id")
        self.assertEqual(log.requested_mobile, "8888888888")
        self.assertEqual(log.file_path, self.doc.file_relative_path)
        self.assertEqual(log.file_checksum, "abc123")
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        self.tmp.write(b"%PDF-1.4 test content")
        self.tmp.close()

        base_path = os.path.dirname(self.tmp.name)
        rel_path = os.path.basename(self.tmp.name)

        self.doc = Document.objects.create(
            authorization_number="AUTH100",
            document_type="PPO",
            external_system_id="EXT100",
            employee_name="Sunil Kumar",
            employee_dob=date(1990, 12, 31),
            file_relative_path=rel_path,
        )

        self._base_path_patcher = patch.object(
            settings, "DIGILOCKER_BASE_STORAGE_PATH", base_path
        )
        self._base_path_patcher.start()

    def tearDown(self):
        self._base_path_patcher.stop()
        os.unlink(self.tmp.name)

    def _make_signed_request(self, body: bytes):
        key = settings.DIGILOCKER_API_KEY.encode()
        return base64.b64encode(
            hmac_mod.new(key, body, hashlib.sha256).digest()
        ).decode()

    def test_pull_uri_success(self):
        ts = timezone.now().isoformat()
        keyhash = hashlib.sha256(
            (settings.DIGILOCKER_API_KEY + ts).encode()
        ).hexdigest()

        body = (
            f'<?xml version="1.0" encoding="UTF-8"?>'
            f'<PullURIRequest xmlns="http://tempuri.org/" ver="3.0"'
            f' ts="{ts}" txn="test-txn"'
            f' orgId="{settings.DIGILOCKER_ISSUER_ID}"'
            f' keyhash="{keyhash}" format="both">'
            f"<DocDetails>"
            f"<DocType>PPO</DocType>"
            f"<DigiLockerId>dl-test</DigiLockerId>"
            f"<FullName>Sunil Kumar</FullName>"
            f"<DOB>31-12-1990</DOB>"
            f"<UDF1>AUTH100</UDF1>"
            f"</DocDetails>"
            f"</PullURIRequest>"
        ).encode()

        hmac_sig = self._make_signed_request(body)

        response = self.client.post(
            "/issuer/pull-uri",
            data=body,
            content_type="application/xml",
            HTTP_X_DIGILOCKER_HMAC=hmac_sig,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Status="1"', response.content)
        self.assertIn(b"<URI>", response.content)

        self.assertTrue(AccessLog.objects.filter(txn_id="test-txn").exists())

    def test_pull_uri_success_without_dob(self):
        ts = timezone.now().isoformat()
        keyhash = hashlib.sha256(
            (settings.DIGILOCKER_API_KEY + ts).encode()
        ).hexdigest()

        body = (
            f'<?xml version="1.0" encoding="UTF-8"?>'
            f'<PullURIRequest xmlns="http://tempuri.org/" ver="3.0"'
            f' ts="{ts}" txn="test-txn-no-dob"'
            f' orgId="{settings.DIGILOCKER_ISSUER_ID}"'
            f' keyhash="{keyhash}" format="both">'
            f"<DocDetails>"
            f"<DocType>PPO</DocType>"
            f"<DigiLockerId>dl-test</DigiLockerId>"
            f"<FullName>Sunil Kumar</FullName>"
            f"<UDF1>AUTH100</UDF1>"
            f"</DocDetails>"
            f"</PullURIRequest>"
        ).encode()

        hmac_sig = self._make_signed_request(body)

        response = self.client.post(
            "/issuer/pull-uri",
            data=body,
            content_type="application/xml",
            HTTP_X_DIGILOCKER_HMAC=hmac_sig,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Status="1"', response.content)

    def test_pull_uri_ignores_mismatched_dob(self):
        ts = timezone.now().isoformat()
        keyhash = hashlib.sha256(
            (settings.DIGILOCKER_API_KEY + ts).encode()
        ).hexdigest()

        body = (
            f'<?xml version="1.0" encoding="UTF-8"?>'
            f'<PullURIRequest xmlns="http://tempuri.org/" ver="3.0"'
            f' ts="{ts}" txn="test-txn-wrong-dob"'
            f' orgId="{settings.DIGILOCKER_ISSUER_ID}"'
            f' keyhash="{keyhash}" format="both">'
            f"<DocDetails>"
            f"<DocType>PPO</DocType>"
            f"<DigiLockerId>dl-test</DigiLockerId>"
            f"<FullName>Sunil Kumar</FullName>"
            f"<DOB>01-01-2000</DOB>"
            f"<UDF1>AUTH100</UDF1>"
            f"</DocDetails>"
            f"</PullURIRequest>"
        ).encode()

        hmac_sig = self._make_signed_request(body)

        response = self.client.post(
            "/issuer/pull-uri",
            data=body,
            content_type="application/xml",
            HTTP_X_DIGILOCKER_HMAC=hmac_sig,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Status="1"', response.content)

    def test_pull_uri_no_hmac_returns_401(self):
        body = (
            b'<PullURIRequest xmlns="http://tempuri.org/" ver="3.0"'
            b' ts="now" txn="1" orgId="x" keyhash="y">'
            b"<DocDetails><DocType>PPO</DocType>"
            b"<DigiLockerId>x</DigiLockerId>"
            b"<UDF1>PPO123456</UDF1>"
            b"</DocDetails></PullURIRequest>"
        )
        response = self.client.post(
            "/issuer/pull-uri",
            data=body,
            content_type="application/xml",
        )
        self.assertEqual(response.status_code, 401)

    def test_pull_uri_get_not_allowed(self):
        response = self.client.get("/issuer/pull-uri")
        self.assertEqual(response.status_code, 405)
