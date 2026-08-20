"""Tests for PullURIResponse XML construction."""

from datetime import date
from unittest.mock import patch

from django.test import TestCase, override_settings
from lxml import etree

from issuer.models import Document
from issuer.services.response_builder import build_error_response, build_success_response


class ResponseBuilderTest(TestCase):
    def _build_success_response(self, requested_format):
        doc = Document(
            employee_name="Test",
            employee_dob=date(1990, 1, 1),
        )
        return build_success_response(
            doc, "issuer-PECER-ABC123",
            "2024-01-01T00:00:00", "txn1",
            "cGRm", "bWV0YQ==",
            requested_format=requested_format,
        )

    def test_success_response_contains_uri(self):
        xml = self._build_success_response("both")
        self.assertIn(b"issuer-PECER-ABC123", xml)
        self.assertIn(b'Status="1"', xml)

    def test_xml_format_omits_doc_content(self):
        root = etree.fromstring(self._build_success_response("xml"))

        self.assertIsNone(root.find("DocDetails/DocContent"))
        self.assertEqual(root.findtext("DocDetails/DataContent"), "bWV0YQ==")

    def test_pdf_and_both_formats_include_doc_content(self):
        for requested_format in ("pdf", "both", " PDF "):
            with self.subTest(requested_format=requested_format):
                root = etree.fromstring(
                    self._build_success_response(requested_format)
                )
                self.assertEqual(root.findtext("DocDetails/DocContent"), "cGRm")
                self.assertEqual(
                    root.findtext("DocDetails/DataContent"), "bWV0YQ=="
                )

    @override_settings(ISSUER_VERBOSE_LOGGING=True)
    def test_verbose_logging_reports_format_decision(self):
        with self.assertLogs("issuer", level="DEBUG") as captured:
            self._build_success_response("xml")

        diagnostics = next(
            line for line in captured.output
            if "pull_doc.request_format" in line
        )
        self.assertIn("requested_format=xml", diagnostics)
        self.assertIn("doc_content_included=False", diagnostics)

    @override_settings(ISSUER_VERBOSE_LOGGING=False)
    @patch("issuer.services.pull_doc_log.logger.log")
    def test_verbose_logging_is_silent_when_disabled(self, log_mock):
        self._build_success_response("xml")

        log_mock.assert_not_called()

    def test_error_response_status_zero(self):
        xml = build_error_response("2024-01-01T00:00:00", "txn1")
        self.assertIn(b'Status="0"', xml)
