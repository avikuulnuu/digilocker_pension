"""Build PullURIResponse XML per DLTS v1.13 spec."""

from lxml import etree

from issuer.models import Document
from issuer.services.pull_doc_log import request_format_diagnostics

NS = "http://tempuri.org/"


def build_success_response(doc: Document, uri: str, timestamp: str, txn: str,
                           doc_content_b64: str, data_content_b64: str,
                           requested_format: str = "xml") -> bytes:
    """Build a successful PullURIResponse XML."""
    root = etree.Element("PullURIResponse", nsmap={"ns2": NS})

    status_el = etree.SubElement(root, "ResponseStatus",
                                  Status="1", ts=timestamp, txn=txn)
    status_el.text = "1"

    doc_details = etree.SubElement(root, "DocDetails")

    # IssuedTo / Persons / Person
    issued_to = etree.SubElement(doc_details, "IssuedTo")
    persons = etree.SubElement(issued_to, "Persons")
    person_attrs = {"name": doc.employee_name or ""}
    if doc.employee_dob:
        person_attrs["dob"] = doc.employee_dob.strftime("%d-%m-%Y")
    etree.SubElement(persons, "Person", **person_attrs)

    # URI
    uri_el = etree.SubElement(doc_details, "URI")
    uri_el.text = uri

    normalized_format = requested_format.strip().lower()
    doc_content_included = normalized_format in {"pdf", "both"}
    request_format_diagnostics(
        txn=txn,
        requested_format=(
            normalized_format
            if normalized_format in {"xml", "pdf", "both"}
            else "unsupported"
        ),
        doc_content_included=doc_content_included,
    )

    # DocContent (Base64 PDF)
    if doc_content_included:
        doc_content_el = etree.SubElement(doc_details, "DocContent")
        doc_content_el.text = doc_content_b64

    # DataContent (Base64 XML metadata)
    data_content_el = etree.SubElement(doc_details, "DataContent")
    data_content_el.text = data_content_b64

    return etree.tostring(root, xml_declaration=True, encoding="UTF-8",
                          pretty_print=True)


def build_error_response(timestamp: str, txn: str) -> bytes:
    """Build a failure PullURIResponse (Status=0)."""
    root = etree.Element("PullURIResponse", nsmap={"ns2": NS})
    status_el = etree.SubElement(root, "ResponseStatus",
                                  Status="0", ts=timestamp, txn=txn)
    status_el.text = "0"
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8",
                          pretty_print=True)


def build_pending_response(timestamp: str, txn: str) -> bytes:
    """Build a pending PullURIResponse (Status=9)."""
    root = etree.Element("PullURIResponse", nsmap={"ns2": NS})
    status_el = etree.SubElement(root, "ResponseStatus",
                                  Status="9", ts=timestamp, txn=txn)
    status_el.text = "9"
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8",
                          pretty_print=True)
