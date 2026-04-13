"""Tests for HMAC, KeyHash, and timestamp authentication."""

import base64
import hashlib
import hmac as hmac_mod

from django.conf import settings
from django.test import TestCase
from django.utils import timezone

from issuer.authentication import AuthenticationError, verify_hmac, verify_keyhash, verify_timestamp


class HMACVerificationTest(TestCase):
    def test_valid_hmac(self):
        body = b"<PullURIRequest>test</PullURIRequest>"
        key = settings.DIGILOCKER_API_KEY.encode()
        sig = base64.b64encode(
            hmac_mod.new(key, body, hashlib.sha256).digest()
        ).decode()
        verify_hmac(body, sig)

    def test_invalid_hmac_raises(self):
        with self.assertRaises(AuthenticationError):
            verify_hmac(b"body", "badsignature")

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
