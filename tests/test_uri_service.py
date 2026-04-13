"""Tests for URI generation and management."""

from datetime import date

from django.conf import settings
from django.test import TestCase

from issuer.models import Document
from issuer.services.uri_service import build_uri, ensure_uri


class URIServiceTest(TestCase):
    def setUp(self):
        self.doc = Document.objects.create(
            authorization_number="AUTH001",
            document_type="PPO",
            employee_name="Test User",
            employee_dob=date(1990, 12, 31),
            file_relative_path="test/doc.pdf",
        )

    def test_build_uri_format(self):
        uri = build_uri("PPO", "XY12345Z")
        self.assertEqual(uri, f"{settings.DIGILOCKER_ISSUER_ID}-PPO-XY12345Z")

    def test_ensure_uri_generates_once(self):
        uri1 = ensure_uri(self.doc.pk)
        uri2 = ensure_uri(self.doc.pk)
        self.assertEqual(uri1, uri2)
        self.doc.refresh_from_db()
        self.assertIsNotNone(self.doc.doc_id)
        self.assertTrue(uri1.startswith(settings.DIGILOCKER_ISSUER_ID))
