"""Document lookup and orchestration service."""

import base64
import logging

from issuer.models import Document
from issuer.services.file_service import read_file_bytes, FileNotAvailableError, IntegrityCheckError
from issuer.services.identity_validator import validate_identity, IdentityMismatchError
from issuer.services.uri_service import ensure_uri
from issuer.services.xml_parser import PullURIRequestData

logger = logging.getLogger("issuer")


class DocumentNotFoundError(Exception):
    pass


def lookup_document(request_data: PullURIRequestData) -> Document:
    """Find the document matching the request criteria.

    Looks up by authorization_number (from UDF1) + document_type.
    """
    authorization_number = request_data.udfs.get("UDF1", "").strip()
    if not authorization_number:
        raise DocumentNotFoundError("No search identifier (UDF1) provided")

    try:
        doc = Document.objects.get(
            authorization_number=authorization_number,
            document_type=request_data.doc_type,
            is_active=True,
            digilocker_enabled=True,
        )
    except Document.DoesNotExist:
        raise DocumentNotFoundError(
            f"No document found for type={request_data.doc_type} "
            f"auth={authorization_number}"
        )
    return doc


def process_pull_uri(request_data: PullURIRequestData) -> dict:
    """Full pipeline: lookup → identity check → URI → file read → encode.

    Returns a dict with keys: doc, uri, doc_content_b64, data_content_b64.
    Raises DocumentNotFoundError, IdentityMismatchError, FileNotAvailableError,
    or IntegrityCheckError on failure.
    """
    # 1. Lookup
    doc = lookup_document(request_data)

    # 2. Identity validation
    validate_identity(doc, request_data.full_name, request_data.dob)

    # 3. Ensure URI (lazy generation)
    uri = ensure_uri(doc.pk)

    # 4. File read + integrity
    file_bytes = read_file_bytes(doc)

    # 5. Encode
    doc_content_b64 = base64.b64encode(file_bytes).decode("utf-8")

    # DataContent: minimal XML metadata about the document
    metadata_xml = _build_metadata_xml(doc)
    data_content_b64 = base64.b64encode(metadata_xml.encode("utf-8")).decode("utf-8")

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
