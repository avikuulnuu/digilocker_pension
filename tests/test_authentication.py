"""Tests for HMAC, KeyHash, and timestamp authentication."""

import base64
import hashlib
import hmac as hmac_mod

from django.conf import settings
from django.test import TestCase, override_settings
from django.utils import timezone

from issuer.authentication import AuthenticationError, verify_hmac, verify_keyhash, verify_timestamp


class HMACVerificationTest(TestCase):
    @staticmethod
    def _signature(body):
        key = settings.DIGILOCKER_API_KEY.encode()
        return base64.b64encode(
            hmac_mod.new(key, body, hashlib.sha256).digest()
        ).decode()

    @staticmethod
    def _digilocker_hex_signature(body):
        key = settings.DIGILOCKER_API_KEY.encode()
        digest_hex = hmac_mod.new(key, body, hashlib.sha256).hexdigest()
        return base64.b64encode(digest_hex.encode("ascii")).decode()

    @override_settings(DIGILOCKER_HMAC_ENCODING_MODE="STANDARD")
    def test_valid_hmac(self):
        body = b"<PullURIRequest>test</PullURIRequest>"
        verify_hmac(body, self._signature(body))

    @override_settings(DIGILOCKER_HMAC_ENCODING_MODE="STANDARD")
    def test_invalid_hmac_raises(self):
        with self.assertRaises(AuthenticationError):
            verify_hmac(b"body", "badsignature")

    @override_settings(DIGILOCKER_HMAC_ENCODING_MODE="STANDARD")
    def test_standard_mode_rejects_digilocker_hex_signature(self):
        body = b"<PullURIRequest>test</PullURIRequest>"
        with self.assertRaises(AuthenticationError):
            verify_hmac(body, self._digilocker_hex_signature(body))

    @override_settings(DIGILOCKER_HMAC_ENCODING_MODE="DIGILOCKER_HEX")
    def test_digilocker_hex_mode_accepts_hex_encoded_signature(self):
        body = b"<PullURIRequest>test</PullURIRequest>"
        verify_hmac(body, self._digilocker_hex_signature(body))

    @override_settings(
        DIGILOCKER_HMAC_ENCODING_MODE="DIGILOCKER_HEX",
        ISSUER_VERBOSE_LOGGING=True,
    )
    def test_digilocker_hex_diagnostics_recognize_valid_base64(self):
        signed_body = b"<PullURIRequest>test</PullURIRequest>"
        received_hmac = self._digilocker_hex_signature(signed_body)

        with self.assertLogs("issuer", level="DEBUG") as captured:
            with self.assertRaises(AuthenticationError):
                verify_hmac(signed_body + b"\n", received_hmac)

        diagnostics = next(
            line for line in captured.output if "HMAC diagnostics" in line
        )
        self.assertIn("mode=DIGILOCKER_HEX", diagnostics)
        self.assertIn("valid_base64=True", diagnostics)

    @override_settings(DIGILOCKER_HMAC_ENCODING_MODE="DIGILOCKER_HEX")
    def test_digilocker_hex_mode_rejects_standard_signature(self):
        body = b"<PullURIRequest>test</PullURIRequest>"
        with self.assertRaises(AuthenticationError):
            verify_hmac(body, self._signature(body))

    @override_settings(DIGILOCKER_HMAC_ENCODING_MODE="UNKNOWN")
    def test_invalid_hmac_encoding_mode_fails_closed(self):
        body = b"<PullURIRequest>test</PullURIRequest>"
        with self.assertRaisesMessage(
            AuthenticationError,
            "Invalid HMAC encoding configuration",
        ):
            verify_hmac(body, self._signature(body))

    @override_settings(
        DIGILOCKER_HMAC_ENCODING_MODE="STANDARD",
        ISSUER_VERBOSE_LOGGING=False,
    )
    def test_invalid_hmac_diagnostics_disabled(self):
        with self.assertLogs("issuer", level="WARNING") as captured:
            with self.assertRaises(AuthenticationError):
                verify_hmac(b"body", "badsignature")

        self.assertFalse(any("HMAC diagnostics" in line for line in captured.output))

    @override_settings(
        DIGILOCKER_HMAC_ENCODING_MODE="STANDARD",
        ISSUER_VERBOSE_LOGGING=True,
    )
    def test_invalid_hmac_diagnostics_identify_trailing_newline_safely(self):
        signed_body = b"<PullURIRequest>test</PullURIRequest>"
        received_hmac = self._signature(signed_body)
        received_body = signed_body + b"\r\n"

        with self.assertLogs("issuer", level="DEBUG") as captured:
            with self.assertRaises(AuthenticationError):
                verify_hmac(received_body, received_hmac)

        diagnostics = next(
            line for line in captured.output if "HMAC diagnostics" in line
        )
        self.assertIn("mode=STANDARD", diagnostics)
        self.assertIn("valid_base64=True", diagnostics)
        self.assertIn("final_newline=True", diagnostics)
        self.assertIn("matches_without_final_newline=True", diagnostics)
        self.assertNotIn(received_hmac, diagnostics)
        self.assertNotIn(signed_body.decode(), diagnostics)

    def test_valid_keyhash(self):
        ts = "2024-05-21T12:34:56+05:30"
        key = settings.DIGILOCKER_API_KEY
        expected = hashlib.sha256((key + ts).encode()).hexdigest()
        verify_keyhash(expected, ts)

    def test_invalid_keyhash_raises(self):
        with self.assertRaises(AuthenticationError):
            verify_keyhash("badhash", "2024-05-21T12:34:56+05:30")

    def test_timestamp_within_skew(self):
        ts = timezone.now().isoformat()
        verify_timestamp(ts)

    def test_timestamp_outside_skew_raises(self):
        ts = "2020-01-01T00:00:00+05:30"
        with self.assertRaises(AuthenticationError):
            verify_timestamp(ts)
