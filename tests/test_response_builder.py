"""Tests for PullURIResponse XML construction."""

from datetime import date

from django.test import TestCase

from issuer.models import Document
from issuer.services.response_builder import build_error_response, build_success_response


class ResponseBuilderTest(TestCase):
    def test_success_response_contains_uri(self):
        doc = Document(
            employee_name="Test",
            employee_dob=date(1990, 1, 1),
        )
        xml = build_success_response(
            doc, "issuer-PPO-ABC123",
            "2024-01-01T00:00:00", "txn1",
            "cGRm", "bWV0YQ==",
        )
        self.assertIn(b"issuer-PPO-ABC123", xml)
        self.assertIn(b'Status="1"', xml)

    def test_error_response_status_zero(self):
        xml = build_error_response("2024-01-01T00:00:00", "txn1")
        self.assertIn(b'Status="0"', xml)
