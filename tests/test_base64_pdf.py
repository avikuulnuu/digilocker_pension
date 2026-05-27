"""Tests for Base64 PDF decoding helpers and manage portal tool."""

import base64
import re

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, override_settings
from django.urls import reverse

from issuer.models import Document
from issuer.services.base64_pdf import decode_pdf_bytes, normalize_base64_input

User = get_user_model()


def _login_manage_portal(client):
    user = User.objects.create_user(username="decode_tester", password="unused")
    perm = Permission.objects.get(
        codename="access_manage_portal",
        content_type=ContentType.objects.get_for_model(Document),
    )
    user.user_permissions.add(perm)
    client.force_login(user)

_MINIMAL_PDF = b"%PDF-1.4 minimal"


class Base64PdfServiceTest(TestCase):
    def test_normalize_strips_whitespace_and_data_uri_prefix(self):
        raw = "data:application/pdf;base64,\n" + base64.b64encode(_MINIMAL_PDF).decode()
        normalized = normalize_base64_input(raw)
        self.assertEqual(base64.b64decode(normalized), _MINIMAL_PDF)

    def test_decode_pdf_bytes_success(self):
        b64 = base64.b64encode(_MINIMAL_PDF).decode()
        self.assertEqual(decode_pdf_bytes(b64, max_bytes=1024), _MINIMAL_PDF)

    def test_decode_rejects_non_pdf(self):
        b64 = base64.b64encode(b"not a pdf").decode()
        with self.assertRaises(ValueError) as ctx:
            decode_pdf_bytes(b64, max_bytes=1024)
        self.assertIn("not a PDF", str(ctx.exception))

    def test_decode_rejects_oversized(self):
        b64 = base64.b64encode(_MINIMAL_PDF).decode()
        with self.assertRaises(ValueError) as ctx:
            decode_pdf_bytes(b64, max_bytes=4)
        self.assertIn("size limit", str(ctx.exception))


@override_settings(MANAGE_DECODE_PDF_ENABLED=True)
class DecodePdfManageViewTest(TestCase):
    def setUp(self):
        _login_manage_portal(self.client)

    def test_tool_decode_and_view_roundtrip(self):
        b64 = base64.b64encode(_MINIMAL_PDF).decode()
        tool_url = reverse("issuer:decode-pdf-tool")
        response = self.client.post(tool_url, {"base64_input": b64})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "View decoded document")
        match = re.search(
            r"/issuer/manage/tools/decode-pdf/view/[^\"']+",
            response.content.decode(),
        )
        self.assertIsNotNone(match)
        view_response = self.client.get(match.group(0))
        self.assertEqual(view_response.status_code, 200)
        self.assertEqual(view_response["Content-Type"], "application/pdf")
        self.assertEqual(view_response.content, _MINIMAL_PDF)

    def test_tool_shows_error_for_invalid_base64(self):
        tool_url = reverse("issuer:decode-pdf-tool")
        response = self.client.post(tool_url, {"base64_input": "%%%not-base64%%%"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid Base64")

    def test_view_unknown_token_returns_404(self):
        url = reverse("issuer:decode-pdf-view", kwargs={"token": "missing-token"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_anonymous_decode_tool_redirects_to_login(self):
        anonymous = self.client_class()
        response = anonymous.get(reverse("issuer:decode-pdf-tool"))
        self.assertEqual(response.status_code, 302)


@override_settings(MANAGE_DECODE_PDF_ENABLED=False)
class DecodePdfDisabledTest(TestCase):
    def setUp(self):
        _login_manage_portal(self.client)

    def test_tool_returns_404_when_disabled(self):
        response = self.client.get(reverse("issuer:decode-pdf-tool"))
        self.assertEqual(response.status_code, 404)

    def test_view_returns_404_when_disabled(self):
        response = self.client.get(
            reverse("issuer:decode-pdf-view", kwargs={"token": "abc123"})
        )
        self.assertEqual(response.status_code, 404)
