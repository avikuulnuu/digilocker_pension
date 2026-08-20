"""Integration tests for the Pull URI API."""

import base64
import hashlib
import hmac as hmac_mod
import os
import tempfile
from datetime import date
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase, override_settings
from django.utils import timezone

from issuer.models import AccessLog, Document


@override_settings(DIGILOCKER_HMAC_ENCODING_MODE="STANDARD")
class PullURIViewTest(TestCase):
    def setUp(self):
        self.base_path = tempfile.mkdtemp()
        self.file_stem = "test_auth100_ppo"
        file_path = os.path.join(self.base_path, f"{self.file_stem}_signed.pdf")
        with open(file_path, "wb") as f:
            f.write(b"%PDF-1.4 test content")

        self.doc = Document.objects.create(
            authorization_number="AUTH100",
            document_type="PECER",
            external_system_id=2100,
            authorization_date=date(2024, 1, 1),
            employee_name="Sunil Kumar",
            employee_dob=date(1990, 12, 31),
            file_name=self.file_stem,
        )

        self._base_path_patcher = patch.object(
            settings, "DIGILOCKER_BASE_STORAGE_PATH", self.base_path
        )
        self._base_path_patcher.start()

    def tearDown(self):
        self._base_path_patcher.stop()
        file_path = os.path.join(self.base_path, f"{self.file_stem}_signed.pdf")
        if os.path.exists(file_path):
            os.unlink(file_path)
        os.rmdir(self.base_path)

    def _make_signed_request(self, body: bytes):
        key = settings.DIGILOCKER_API_KEY.encode()
        return base64.b64encode(
            hmac_mod.new(key, body, hashlib.sha256).digest()
        ).decode()

    def _make_digilocker_hex_signed_request(self, body: bytes):
        key = settings.DIGILOCKER_API_KEY.encode()
        digest_hex = hmac_mod.new(key, body, hashlib.sha256).hexdigest()
        return base64.b64encode(digest_hex.encode("ascii")).decode()

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
            f"<DocType>PECER</DocType>"
            f"<DigiLockerId>dl-test</DigiLockerId>"
            f"<FullName>Sunil Kumar</FullName>"
            f"<DOB>31-12-1990</DOB>"
            f"<AUTHN>AUTH100</AUTHN>"
            f"</DocDetails>"
            f"</PullURIRequest>"
        ).encode()

        hmac_sig = self._make_signed_request(body)

        response = self.client.post(
            "/api/pulluri",
            data=body,
            content_type="application/xml",
            HTTP_X_DIGILOCKER_HMAC=hmac_sig,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Status="1"', response.content)
        self.assertIn(b"<URI>", response.content)
        self.assertIn(b"<DocContent>", response.content)
        self.assertIn(b"<DataContent>", response.content)

        self.assertTrue(AccessLog.objects.filter(txn_id="test-txn").exists())

        self.doc.refresh_from_db()
        self.assertEqual(self.doc.access_count, 1)
        self.assertIsNotNone(self.doc.last_accessed_at)

    def test_pull_uri_xml_format_omits_doc_content(self):
        ts = timezone.now().isoformat()
        keyhash = hashlib.sha256(
            (settings.DIGILOCKER_API_KEY + ts).encode()
        ).hexdigest()
        body = (
            f'<?xml version="1.0" encoding="UTF-8"?>'
            f'<PullURIRequest xmlns="http://tempuri.org/" ver="3.0"'
            f' ts="{ts}" txn="test-txn-xml-format"'
            f' orgId="{settings.DIGILOCKER_ISSUER_ID}"'
            f' keyhash="{keyhash}" format="xml">'
            f"<DocDetails>"
            f"<DocType>PECER</DocType>"
            f"<DigiLockerId>dl-test</DigiLockerId>"
            f"<FullName>Sunil Kumar</FullName>"
            f"<DOB>31-12-1990</DOB>"
            f"<AUTHN>AUTH100</AUTHN>"
            f"</DocDetails>"
            f"</PullURIRequest>"
        ).encode()

        response = self.client.post(
            "/api/pulluri",
            data=body,
            content_type="application/xml",
            HTTP_X_DIGILOCKER_HMAC=self._make_signed_request(body),
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b"<DocContent>", response.content)
        self.assertIn(b"<DataContent>", response.content)

    def test_pull_uri_success_with_digilocker_issuer_namespace(self):
        ts = timezone.now().isoformat()
        keyhash = hashlib.sha256(
            (settings.DIGILOCKER_API_KEY + ts).encode()
        ).hexdigest()
        body = (
            f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<PullURIRequest xmlns="https://www.digitallocker.gov.in/schema/issuer/v1/pullurirequest"'
            f' ver="3.0" ts="{ts}" txn="digilocker-namespace-txn"'
            f' orgId="{settings.DIGILOCKER_ISSUER_ID}"'
            f' keyhash="{keyhash}" format="pdf">'
            f"<DocDetails>"
            f"<DocType>PECER</DocType>"
            f"<FullName>Sunil Kumar</FullName>"
            f"<DOB>31-12-1990</DOB>"
            f"<DigiLockerId>test-digilocker-id</DigiLockerId>"
            f"<AUTHN>AUTH100</AUTHN>"
            f"</DocDetails>"
            f"</PullURIRequest>"
        ).encode()

        response = self.client.post(
            "/api/pulluri",
            data=body,
            content_type="application/xml",
            HTTP_X_DIGILOCKER_HMAC=self._make_signed_request(body),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Status="1"', response.content)
        self.assertTrue(
            AccessLog.objects.filter(txn_id="digilocker-namespace-txn").exists()
        )
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.access_count, 1)

    @override_settings(DIGILOCKER_HMAC_ENCODING_MODE="DIGILOCKER_HEX")
    def test_pull_uri_accepts_digilocker_hex_hmac_mode(self):
        ts = timezone.now().isoformat()
        keyhash = hashlib.sha256(
            (settings.DIGILOCKER_API_KEY + ts).encode()
        ).hexdigest()
        body = (
            f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<PullURIRequest xmlns="https://www.digitallocker.gov.in/schema/issuer/v1/pullurirequest"'
            f' ver="3.0" ts="{ts}" txn="digilocker-hex-txn"'
            f' orgId="{settings.DIGILOCKER_ISSUER_ID}"'
            f' keyhash="{keyhash}" format="pdf">'
            f"<DocDetails>"
            f"<DocType>PECER</DocType>"
            f"<FullName>Sunil Kumar</FullName>"
            f"<DigiLockerId>test-digilocker-id</DigiLockerId>"
            f"<AUTHN>AUTH100</AUTHN>"
            f"</DocDetails>"
            f"</PullURIRequest>"
        ).encode()

        response = self.client.post(
            "/api/pulluri",
            data=body,
            content_type="application/xml",
            HTTP_X_DIGILOCKER_HMAC=self._make_digilocker_hex_signed_request(body),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Status="1"', response.content)
        self.assertTrue(
            AccessLog.objects.filter(txn_id="digilocker-hex-txn").exists()
        )

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
            f"<DocType>PECER</DocType>"
            f"<DigiLockerId>dl-test</DigiLockerId>"
            f"<FullName>Sunil Kumar</FullName>"
            f"<AUTHN>AUTH100</AUTHN>"
            f"</DocDetails>"
            f"</PullURIRequest>"
        ).encode()

        hmac_sig = self._make_signed_request(body)

        response = self.client.post(
            "/api/pulluri",
            data=body,
            content_type="application/xml",
            HTTP_X_DIGILOCKER_HMAC=hmac_sig,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Status="1"', response.content)

    def test_pull_uri_failure_does_not_update_access_stats(self):
        ts = timezone.now().isoformat()
        keyhash = hashlib.sha256(
            (settings.DIGILOCKER_API_KEY + ts).encode()
        ).hexdigest()

        body = (
            f'<?xml version="1.0" encoding="UTF-8"?>'
            f'<PullURIRequest xmlns="http://tempuri.org/" ver="3.0"'
            f' ts="{ts}" txn="test-txn-missing-auth"'
            f' orgId="{settings.DIGILOCKER_ISSUER_ID}"'
            f' keyhash="{keyhash}" format="both">'
            f"<DocDetails>"
            f"<DocType>PECER</DocType>"
            f"<DigiLockerId>dl-test</DigiLockerId>"
            f"<FullName>Sunil Kumar</FullName>"
            f"<AUTHN>DOESNOTEXIST</AUTHN>"
            f"</DocDetails>"
            f"</PullURIRequest>"
        ).encode()

        hmac_sig = self._make_signed_request(body)

        response = self.client.post(
            "/api/pulluri",
            data=body,
            content_type="application/xml",
            HTTP_X_DIGILOCKER_HMAC=hmac_sig,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Status="0"', response.content)
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.access_count, 0)
        self.assertIsNone(self.doc.last_accessed_at)

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
            f"<DocType>PECER</DocType>"
            f"<DigiLockerId>dl-test</DigiLockerId>"
            f"<FullName>Sunil Kumar</FullName>"
            f"<DOB>01-01-2000</DOB>"
            f"<AUTHN>AUTH100</AUTHN>"
            f"</DocDetails>"
            f"</PullURIRequest>"
        ).encode()

        hmac_sig = self._make_signed_request(body)

        response = self.client.post(
            "/api/pulluri",
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
            b"<DocDetails><DocType>PECER</DocType>"
            b"<DigiLockerId>x</DigiLockerId>"
            b"<AUTHN>PECER123456</AUTHN>"
            b"</DocDetails></PullURIRequest>"
        )
        response = self.client.post(
            "/api/pulluri",
            data=body,
            content_type="application/xml",
        )
        self.assertEqual(response.status_code, 401)

    def test_pull_uri_get_not_allowed(self):
        response = self.client.get("/api/pulluri")
        self.assertEqual(response.status_code, 405)

    def test_legacy_pull_doc_endpoints_return_404(self):
        for path in ("/api/pulldoc", "/api/pull-doc"):
            for method in ("get", "post"):
                response = getattr(self.client, method)(path)
                self.assertEqual(response.status_code, 404, msg=f"{method.upper()} {path}")
                self.assertIn(b"not available", response.content)

    def test_document_fetch_by_uri_returns_404(self):
        uri = "in.gov.state.department-PECER-TESTDOC01"
        response = self.client.get(
            f"/api/document/{uri}",
            HTTP_X_DIGILOCKER_HMAC="dummy",
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn(b"not available", response.content)
        self.assertFalse(AccessLog.objects.exists())
