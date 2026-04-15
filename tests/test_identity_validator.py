"""Tests for identity validation (name/DOB matching)."""

from datetime import date

from django.test import TestCase, override_settings

from issuer.models import Document
from issuer.services.identity_validator import IdentityMismatchError, validate_identity


@override_settings(DIGILOCKER_IDENTITY_VALIDATION_MODE="STRICT")
class IdentityValidatorStrictTest(TestCase):
    def setUp(self):
        self.doc = Document.objects.create(
            authorization_number="AUTH002",
            document_type="PPO",
            external_system_id=2002,
            authorization_date="01/01/2024",
            employee_name="Sunil Kumar",
            employee_dob=date(1990, 12, 31),
            file_name="test/doc.pdf",
        )

    def test_strict_no_fields_raises(self):
        with self.assertRaises(IdentityMismatchError):
            validate_identity(self.doc, "", "")

    def test_name_match(self):
        validate_identity(self.doc, "sunil kumar", "")

    def test_name_mismatch_raises(self):
        with self.assertRaises(IdentityMismatchError):
            validate_identity(self.doc, "Wrong Name", "")

    def test_dob_only_raises_when_name_missing(self):
        with self.assertRaises(IdentityMismatchError):
            validate_identity(self.doc, "", "31-12-1990")

    def test_dob_is_ignored_when_name_matches(self):
        validate_identity(self.doc, "Sunil Kumar", "01-01-2000")


@override_settings(DIGILOCKER_IDENTITY_VALIDATION_MODE="LENIENT")
class IdentityValidatorLenientTest(TestCase):
    def setUp(self):
        self.doc = Document.objects.create(
            authorization_number="AUTH003",
            document_type="PPO",
            external_system_id=2003,
            authorization_date="01/01/2024",
            employee_name="Test User",
            employee_dob=date(1990, 12, 31),
            file_name="test/doc.pdf",
        )

    def test_lenient_no_fields_ok(self):
        validate_identity(self.doc, "", "")

    def test_lenient_dob_only_is_ignored(self):
        validate_identity(self.doc, "", "01-01-2000")
