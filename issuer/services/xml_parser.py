"""Parse incoming PullURIRequest XML from DigiLocker."""

import logging
from dataclasses import dataclass, field
from xml.etree.ElementTree import ParseError

from lxml import etree

logger = logging.getLogger("issuer")

NS = {"dl": "http://tempuri.org/"}


class XMLParseError(Exception):
    """Raised when XML request cannot be parsed or is missing required fields."""


@dataclass
class PullURIRequestData:
    ver: str = ""
    timestamp: str = ""
    txn: str = ""
    org_id: str = ""
    keyhash: str = ""
    format: str = "xml"
    doc_type: str = ""
    digilocker_id: str = ""
    uid: str = ""
    full_name: str = ""
    dob: str = ""
    photo: str = ""
    udfs: dict = field(default_factory=dict)


def parse_pull_uri_request(raw_xml: bytes) -> PullURIRequestData:
    """Parse raw XML bytes into a PullURIRequestData object.

    Validates that all mandatory fields are present.
    """
    try:
        root = etree.fromstring(raw_xml)
    except etree.XMLSyntaxError as exc:
        raise XMLParseError(f"Malformed XML: {exc}") from exc

    data = PullURIRequestData()

    # Root attributes
    data.ver = root.get("ver", "")
    data.timestamp = root.get("ts", "")
    data.txn = root.get("txn", "")
    data.org_id = root.get("orgId", "")
    data.keyhash = root.get("keyhash", "")
    data.format = root.get("format", "xml")

    # Mandatory root attributes
    for attr_name, attr_val in [("ver", data.ver), ("ts", data.timestamp),
                                 ("txn", data.txn), ("orgId", data.org_id)]:
        if not attr_val:
            raise XMLParseError(f"Missing mandatory attribute: {attr_name}")

    # DocDetails
    doc_details = root.find("dl:DocDetails", NS)
    if doc_details is None:
        # Try without namespace
        doc_details = root.find("DocDetails")
    if doc_details is None:
        raise XMLParseError("Missing DocDetails element")

    def _text(parent, tag):
        el = parent.find(f"dl:{tag}", NS)
        if el is None:
            el = parent.find(tag)
        return (el.text or "").strip() if el is not None else ""

    data.doc_type = _text(doc_details, "DocType")
    data.digilocker_id = _text(doc_details, "DigiLockerId")
    data.uid = _text(doc_details, "UID")
    data.full_name = _text(doc_details, "FullName")
    data.dob = _text(doc_details, "DOB")
    data.photo = _text(doc_details, "Photo")

    if not data.doc_type:
        raise XMLParseError("Missing mandatory element: DocType")

    # Collect UDFs (UDF1, UDF2, ... UDFn)
    for child in doc_details:
        tag = etree.QName(child).localname
        if tag.upper().startswith("UDF"):
            data.udfs[tag] = (child.text or "").strip()

    return data
