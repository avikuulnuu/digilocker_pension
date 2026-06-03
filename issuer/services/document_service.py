"""Document lookup and orchestration service."""

import base64
import logging

from issuer.models import Document
from issuer.services.file_service import (
    FileNotAvailableError,
    IntegrityCheckError,
    _db_file_stem,
    find_readable_path,
    read_file_bytes,
    resolve_path,
)
from issuer.services.identity_validator import validate_identity, IdentityMismatchError
from issuer.services.pull_doc_log import stage_failed, stage_ok
from issuer.services.uri_service import ensure_uri
from issuer.services.xml_parser import PullURIRequestData

logger = logging.getLogger("issuer")


class DocumentNotFoundError(Exception):
    """Document could not be resolved for Pull URI lookup."""

    def __init__(self, message, *, reason_code=""):
        super().__init__(message)
        self.reason_code = reason_code


def _fail_lookup(reason_code, message, *, txn="", **context):
    stage_failed("lookup", message, reason_code=reason_code, txn=txn, **context)
    raise DocumentNotFoundError(message, reason_code=reason_code)


def _fail_file_unavailable(reason_code, message, *, txn="", **context):
    stage_failed("file_read", message, reason_code=reason_code, txn=txn, **context)
    raise FileNotAvailableError(message)


def lookup_document(request_data: PullURIRequestData, *, txn: str = "") -> Document:
    """Find the document matching the request criteria.

    Looks up by authorization_number (from UDF1) + document_type, with detailed
    diagnostics when the record or stored file cannot be resolved.
    """
    authorization_number = request_data.udfs.get("UDF1", "").strip()
    doc_type = (request_data.doc_type or "").strip()
    logger.info(
        "pull_doc.lookup: UDF1=%r doc_type=%r txn=%s",
        authorization_number,
        doc_type,
        txn,
    )
    if not authorization_number:
        _fail_lookup(
            "MISSING_UDF1",
            "No search identifier (UDF1) provided in the request",
            txn=txn,
            doc_type=doc_type,
        )

    by_auth = Document.objects.filter(authorization_number=authorization_number)
    if not by_auth.exists():
        message = (
            f"No document record exists for authorization number '{authorization_number}'"
        )
        file_match = Document.objects.filter(file_name=authorization_number).first()
        if not file_match:
            effective = effective_file_name(authorization_number)
            if effective != authorization_number:
                file_match = Document.objects.filter(file_name=effective).first()
        if file_match:
            message = (
                f"No document with authorization_number '{authorization_number}', but "
                f"file_name '{file_match.file_name}' exists on document id={file_match.pk} "
                f"(authorization_number='{file_match.authorization_number}', "
                f"document_type='{file_match.document_type}'). "
                f"Pull URI UDF1 must match authorization_number, not file_name."
            )
        _fail_lookup(
            "AUTH_NOT_FOUND",
            message,
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
            full_path,
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
    validate_identity(doc, request_data.full_name, request_data.dob)
    stage_ok("identity", "Identity validated", txn=txn, document_id=doc.pk)

    # 3. Ensure URI (lazy generation)
    uri = ensure_uri(doc.pk)
    stage_ok("uri", "URI ready", txn=txn, document_id=doc.pk, uri=uri)

    # 4. File read + integrity
    file_bytes = read_file_bytes(
        doc,
        request_ip=request_ip,
        digilocker_txn=txn,
        digilocker_id=digilocker_id or request_data.digilocker_id,
    )

    # 5. Encode
    doc_content_b64 = base64.b64encode(file_bytes).decode("utf-8")
    metadata_xml = _build_metadata_xml(doc)
    data_content_b64 = base64.b64encode(metadata_xml.encode("utf-8")).decode("utf-8")
    stage_ok("encode", "Response payload encoded", txn=txn, document_id=doc.pk)

    return {
        "doc": doc,
        "uri": uri,
        "doc_content_b64": doc_content_b64,
        "data_content_b64": data_content_b64,
    }


def _build_metadata_xml(doc: Document) -> str:
    """Build a simple certificate metadata XML for DataContent."""
    dob_str = doc.employee_dob.strftime("%d-%m-%Y") if doc.employee_dob else ""
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f"<CertificateData>"
        f"<Name>{doc.employee_name or ''}</Name>"
        f"<Gender>{doc.employee_gender or ''}</Gender>"
        f"<Mobile>{doc.employee_mobile or ''}</Mobile>"
        f"<DOB>{dob_str}</DOB>"
        f"<AuthorizationNumber>{doc.authorization_number}</AuthorizationNumber>"
        f"<AuthorizationDate>{doc.authorization_date or ''}</AuthorizationDate>"
        f"<DocumentType>{doc.document_type}</DocumentType>"
        f"<DDOName>{doc.ddo_name or ''}</DDOName>"
        f"<TreasuryName>{doc.treasury_name or ''}</TreasuryName>"
        f"<ApplicationNumber>{doc.application_number or ''}</ApplicationNumber>"
        f"<ExternalSystemId>{doc.external_system_id or ''}</ExternalSystemId>"
        f"</CertificateData>"
    )
