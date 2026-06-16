"""Tests for DataContent certificate metadata XML."""

import base64
from datetime import date

from django.test import TestCase
from lxml import etree

from issuer.models import Document
from issuer.services.document_service import _build_metadata_xml


class MetadataXMLTest(TestCase):
    def test_certificate_structure(self):
        doc = Document(
            authorization_number="AUTH100",
            document_type="PECER",
            external_system_id="1070751",
            authorization_date=date(2026, 4, 15),
            employee_name="Sunil Kumar",
            employee_dob=date(1990, 12, 31),
            employee_gender="M",
            employee_mobile="9852185555",
            ddo_name="Medical and Health Officer",
            treasury_name="Nongstoin Treasury",
            is_active=True,
        )
        xml = _build_metadata_xml(doc)
        root = etree.fromstring(xml.encode("utf-8"))

        self.assertEqual(root.tag, "Certificate")
        self.assertEqual(root.get("type"), "PECER")
        self.assertEqual(root.get("number"), "AUTH100")
        self.assertEqual(root.get("status"), "A")
        self.assertEqual(root.get("issuedate"), "15/04/2026")

        person = root.find("IssuedTo/Person")
        self.assertIsNotNone(person)
        self.assertEqual(person.get("name"), "Sunil Kumar")
        self.assertEqual(person.get("phone"), "9852185555")

        cert_data = root.find("CertificateData")
        self.assertEqual(cert_data.findtext("GENumber"), "1070751")
        self.assertEqual(cert_data.findtext("Designation"), "Medical and Health Officer")
        self.assertEqual(cert_data.findtext("TreasuryDivision"), "Nongstoin Treasury")
        self.assertIsNotNone(root.find("Signature"))

    def test_metadata_is_base64_encodable(self):
        doc = Document(
            authorization_number="AUTH100",
            document_type="PECER",
            external_system_id="1",
            authorization_date=date(2024, 1, 1),
            employee_name="Test",
            is_active=True,
        )
        xml = _build_metadata_xml(doc)
        encoded = base64.b64encode(xml.encode("utf-8")).decode("utf-8")
        self.assertTrue(encoded)
