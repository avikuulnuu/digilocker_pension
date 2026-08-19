"""Tests for PullURIRequest XML parsing."""

from django.test import TestCase

from issuer.services.xml_parser import XMLParseError, parse_pull_uri_request


class XMLParserTest(TestCase):
    VALID_XML = (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<PullURIRequest xmlns="http://tempuri.org/" ver="3.0"'
        b' ts="2024-05-21T12:34:56+05:30" txn="txn123"'
        b' orgId="in.gov.state.department" keyhash="abc123" format="both">'
        b"<DocDetails>"
        b"<DocType>PECER</DocType>"
        b"<DigiLockerId>dl123</DigiLockerId>"
        b"<FullName>Sunil Kumar</FullName>"
        b"<DOB>31-12-1990</DOB>"
        b"<AUTHN>AUTH001</AUTHN>"
        b"</DocDetails>"
        b"</PullURIRequest>"
    )

    def test_parse_valid_request(self):
        data = parse_pull_uri_request(self.VALID_XML)
        self.assertEqual(data.ver, "3.0")
        self.assertEqual(data.txn, "txn123")
        self.assertEqual(data.doc_type, "PECER")
        self.assertEqual(data.full_name, "Sunil Kumar")
        self.assertEqual(data.dob, "31-12-1990")
        self.assertEqual(data.udfs.get("AUTHN"), "AUTH001")

    def test_parse_request_with_digilocker_issuer_namespace(self):
        xml = b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<PullURIRequest xmlns="https://www.digitallocker.gov.in/schema/issuer/v1/pullurirequest" ver="3.0" ts="2026-08-19T13:53:07+05:30" txn="1787127787" orgId="in.gov.nagaland" keyhash="abc123" format="pdf">
    <DocDetails>
        <DocType>
            GPFFP
        </DocType>
        <FullName>
            Test User
        </FullName>
        <DOB>
            20-02-1970
        </DOB>
        <DigiLockerId>
            test-digilocker-id
        </DigiLockerId>
        <AUTHN>
            TEST12054
        </AUTHN>
    </DocDetails>
</PullURIRequest>'''

        data = parse_pull_uri_request(xml)

        self.assertEqual(data.org_id, "in.gov.nagaland")
        self.assertEqual(data.format, "pdf")
        self.assertEqual(data.doc_type, "GPFFP")
        self.assertEqual(data.full_name, "Test User")
        self.assertEqual(data.dob, "20-02-1970")
        self.assertEqual(data.digilocker_id, "test-digilocker-id")
        self.assertEqual(data.udfs.get("AUTHN"), "TEST12054")

    def test_malformed_xml_raises(self):
        with self.assertRaises(XMLParseError):
            parse_pull_uri_request(b"not xml")

    def test_missing_doc_type_raises(self):
        xml = (
            b'<PullURIRequest xmlns="http://tempuri.org/" ver="3.0"'
            b' ts="now" txn="1" orgId="x" keyhash="y">'
            b"<DocDetails></DocDetails>"
            b"</PullURIRequest>"
        )
        with self.assertRaises(XMLParseError):
            parse_pull_uri_request(xml)
