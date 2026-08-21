"""Document lookup and orchestration service."""

import base64
import logging

from django.conf import settings
from lxml import etree

from issuer.models import Document
from issuer.services.file_service import (
    FileNotAvailableError,
    IntegrityCheckError,
    find_readable_path,
    read_file_bytes,
    resolve_path,
)
from issuer.services.identity_validator import validate_identity, IdentityMismatchError
from issuer.services.pull_doc_log import stage_failed, stage_ok
from issuer.services.uri_service import ensure_uri
from issuer.services.xml_parser import AUTHN_TAG, PullURIRequestData
from issuer.log_safety import mask_identifier, mask_path

logger = logging.getLogger("issuer")

DOC_TYPE_DISPLAY_NAMES = {
    "PECER": "Pensioner's Certificate",
    "PCPYO": "Commutation Payment Order",
    "GRPYO": "Gratuity Payment Order",
    "GPFFP": "GPF Final Payment",
}


class DocumentNotFoundError(Exception):
    """Document could not be resolved for Pull URI lookup."""

    def __init__(self, message, *, reason_code="", document=None):
        super().__init__(message)
        self.reason_code = reason_code
        self.document = document


def _fail_lookup(reason_code, message, *, txn="", **context):
    document = context.pop("document", None)
    stage_failed("lookup", reason_code, reason_code=reason_code, txn=txn, **context)
    raise DocumentNotFoundError(
        message,
        reason_code=reason_code,
        document=document,
    )


def _fail_file_unavailable(reason_code, message, *, txn="", **context):
    document = context.pop("document", None)
    stage_failed("file_read", reason_code, reason_code=reason_code, txn=txn, **context)
    raise FileNotAvailableError(
        message,
        document=document,
        reason_code=reason_code,
    )


def lookup_document(request_data: PullURIRequestData, *, txn: str = "") -> Document:
    """Find the document matching the request criteria.

    Looks up by authorization_number (from AUTHN) + document_type, with detailed
    diagnostics when the record or stored file cannot be resolved.
    """
    authorization_number = request_data.udfs.get(AUTHN_TAG, "").strip()
    doc_type = (request_data.doc_type or "").strip()
    logger.info(
        "pull_doc.lookup: starting lookup doc_type=%r txn=%s document_id_hint=%s",
        doc_type,
        txn,
        mask_identifier(authorization_number) if authorization_number else "",
    )
    if not authorization_number:
        _fail_lookup(
            "MISSING_AUTHN",
            "No search identifier (AUTHN) provided in the request",
            txn=txn,
            doc_type=doc_type,
        )

    by_auth = Document.objects.filter(authorization_number=authorization_number)
    if not by_auth.exists():
        _fail_lookup(
            "AUTH_NOT_FOUND",
            f"No document record exists for authorization number '{authorization_number}'",
            txn=txn,
            doc_type=doc_type,
            authorization_number=authorization_number,
        )

    doc = by_auth.filter(document_type=doc_type).first()
    if doc is None:
        registered_types = list(
            by_auth.values_list("document_type", flat=True).distinct()
        )
        _fail_lookup(
            "DOC_TYPE_MISMATCH",
            (
                f"Authorization '{authorization_number}' exists but no '{doc_type}' "
                f"document is registered. Available types: {', '.join(registered_types)}"
            ),
            txn=txn,
            doc_type=doc_type,
            authorization_number=authorization_number,
            registered_types=",".join(registered_types),
        )

    if not doc.is_active:
        _fail_lookup(
            "DOCUMENT_INACTIVE",
            (
                f"Document {doc_type}/{authorization_number} exists (id={doc.pk}) "
                "but is marked inactive (is_active=False)"
            ),
            txn=txn,
            document=doc,
            document_id=doc.pk,
            doc_type=doc_type,
            authorization_number=authorization_number,
        )

    if not doc.digilocker_enabled:
        _fail_lookup(
            "DIGILOCKER_DISABLED",
            (
                f"Document {doc_type}/{authorization_number} exists (id={doc.pk}) "
                "but DigiLocker access is disabled (digilocker_enabled=False)"
            ),
            txn=txn,
            document=doc,
            document_id=doc.pk,
            doc_type=doc_type,
            authorization_number=authorization_number,
        )

    if not (doc.file_name or "").strip():
        _fail_file_unavailable(
            "FILE_NAME_EMPTY",
            (
                f"Document {doc_type}/{authorization_number} (id={doc.pk}) has no "
                "file_name stored in the database"
            ),
            txn=txn,
            document=doc,
            document_id=doc.pk,
            authorization_number=authorization_number,
        )

    full_path = find_readable_path(doc)
    if not full_path:
        expected = resolve_path(doc)
        _fail_file_unavailable(
            "FILE_MISSING_ON_DISK",
            (
                f"Document record found (id={doc.pk}) but on-disk file for "
                f"'{doc.file_name}' was not found under storage. "
                f"Primary expected path: '{expected}' (file_exists={doc.file_exists})"
            ),
            txn=txn,
            document=doc,
            document_id=doc.pk,
            file_name=doc.file_name,
            expected_path=expected,
            file_exists_flag=doc.file_exists,
            authorization_number=authorization_number,
        )

    if not doc.file_exists:
        logger.warning(
            "pull_doc.lookup: file on disk but file_exists=False for doc %d path=%s",
            doc.pk,
            mask_path(full_path),
        )

    stage_ok(
        "lookup",
        "Document record and file path verified",
        txn=txn,
        document_id=doc.pk,
        doc_type=doc_type,
        authorization_number=authorization_number,
        file_name=doc.file_name,
        expected_path=full_path,
    )
    return doc


def process_pull_uri(
    request_data: PullURIRequestData,
    *,
    txn: str = "",
    request_ip=None,
    digilocker_id: str = "",
) -> dict:
    """Full pipeline: lookup → identity check → URI → file read → encode.

    Returns a dict with keys: doc, uri, doc_content_b64, data_content_b64.
    Raises DocumentNotFoundError, IdentityMismatchError, FileNotAvailableError,
    or IntegrityCheckError on failure.
    """
    # 1. Lookup
    doc = lookup_document(request_data, txn=txn)

    # 2. Identity validation
    try:
        validate_identity(doc, request_data.full_name, request_data.dob)
    except IdentityMismatchError as exc:
        exc.document = doc
        raise
    stage_ok("identity", "Identity validated", txn=txn, document_id=doc.pk)

    # 3. Ensure URI (lazy generation)
    uri = ensure_uri(doc.pk)
    stage_ok("uri", "URI ready", txn=txn, document_id=doc.pk, uri=uri)

    # 4. File read + integrity
    file_result = read_file_bytes(
        doc,
        request_ip=request_ip,
        digilocker_txn=txn,
        digilocker_id=digilocker_id or request_data.digilocker_id,
    )

    # 5. Encode
    doc_content_b64 = base64.b64encode(file_result.content).decode("utf-8")
    metadata_xml = _build_metadata_xml(doc)
    data_content_b64 = base64.b64encode(metadata_xml.encode("utf-8")).decode("utf-8")
    stage_ok("encode", "Response payload encoded", txn=txn, document_id=doc.pk)

    return {
        "doc": doc,
        "uri": uri,
        "doc_content_b64": doc_content_b64,
        "data_content_b64": data_content_b64,
        "integrity_issue": file_result.integrity_issue,
    }


def _format_date(value) -> str:
    return value.strftime("%d/%m/%Y") if value else ""


def _build_metadata_xml(doc: Document) -> str:
    """Build DLTS certificate metadata XML for DataContent."""
    cert_name = DOC_TYPE_DISPLAY_NAMES.get(
        doc.document_type, doc.document_type or "Certificate"
    )
    auth_date = _format_date(doc.authorization_date)
    dob = _format_date(doc.employee_dob)
    status = "A" if doc.is_active else "I"

    root = etree.Element(
        "Certificate",
        language=settings.DIGILOCKER_CERT_LANGUAGE,
        name=cert_name,
        type=doc.document_type or "",
        number=doc.authorization_number or "",
        prevnumber="",
        expirydate="",
        validfromdate="",
        issuedat="",
        issuedate=auth_date,
        status=status,
    )

    issued_by = etree.SubElement(root, "IssuedBy")
    org = etree.SubElement(
        issued_by,
        "Organization",
        name=settings.DIGILOCKER_CERT_ISSUER_NAME,
        code=settings.DIGILOCKER_ISSUER_ID,
        tin="",
        uid="",
        type=settings.DIGILOCKER_CERT_ISSUER_ORG_TYPE,
    )
    etree.SubElement(
        org,
        "Address",
        type=settings.DIGILOCKER_CERT_ISSUER_ADDRESS_TYPE,
        line1=settings.DIGILOCKER_CERT_ISSUER_ADDRESS_LINE1,
        line2="",
        house="",
        landmark="",
        locality="",
        vtc="",
        district="",
        pin=settings.DIGILOCKER_CERT_ISSUER_ADDRESS_PIN,
        state=settings.DIGILOCKER_CERT_ISSUER_ADDRESS_STATE,
        country=settings.DIGILOCKER_CERT_ISSUER_ADDRESS_COUNTRY,
    )

    issued_to = etree.SubElement(root, "IssuedTo")
    person = etree.SubElement(
        issued_to,
        "Person",
        uid="",
        title="",
        name=doc.employee_name or "",
        dob=dob,
        age="",
        RelationName="",
        gender=doc.employee_gender or "",
        category="",
        religion="",
        phone=doc.employee_mobile or "",
        email="",
    )
    etree.SubElement(
        person,
        "Address",
        type="",
        line1="",
        line2="",
        PLOTNo="",
        tax="",
        locality="",
        vtc="",
        district="",
        pin="",
        state="",
        country="IN",
    )

    cert_data = etree.SubElement(root, "CertificateData")
    etree.SubElement(
        cert_data,
        "Certificate",
        name="",
        number="",
        place=doc.treasury_name or settings.DIGILOCKER_CERT_ISSUER_ADDRESS_LINE1,
        date=auth_date,
    )
    ge_number = etree.SubElement(cert_data, "GENumber")
    ge_number.text = str(doc.external_system_id or "")
    designation = etree.SubElement(cert_data, "Designation")
    designation.text = doc.ddo_name or ""
    treasury = etree.SubElement(cert_data, "TreasuryDivision")
    treasury.text = doc.treasury_name or ""

    etree.SubElement(root, "Signature")

    return etree.tostring(
        root, xml_declaration=True, encoding="UTF-8", pretty_print=False
    ).decode("utf-8")
