"""Tests for production log redaction helpers."""

from django.test import SimpleTestCase

from issuer.log_safety import (
    mask_identifier,
    mask_path,
    safe_failure_reason,
    sanitize_log_context,
)


class LogSafetyTest(SimpleTestCase):
    def test_mask_identifier_shows_tail_only(self):
        self.assertEqual(mask_identifier("AUTH12345678"), "***5678")

    def test_mask_path_uses_basename(self):
        self.assertEqual(mask_path("/data/docs/secret/file.pdf"), "file.pdf")

    def test_sanitize_drops_personal_names(self):
        ctx = sanitize_log_context(
            request_name="Alice Example",
            stored_name="Bob Example",
            document_id=42,
        )
        self.assertNotIn("request_name", ctx)
        self.assertNotIn("stored_name", ctx)
        self.assertEqual(ctx["document_id"], 42)

    def test_sanitize_masks_authorization_number(self):
        ctx = sanitize_log_context(authorization_number="AUTH12345678")
        self.assertEqual(ctx["authorization_number"], "***5678")

    def test_safe_failure_reason_uses_reason_code(self):
        class CodedError(Exception):
            reason_code = "AUTH_NOT_FOUND"

        self.assertEqual(safe_failure_reason(CodedError("detailed message")), "AUTH_NOT_FOUND")

    def test_safe_failure_reason_falls_back_to_class_name(self):
        self.assertEqual(safe_failure_reason(ValueError("secret value")), "ValueError")
