"""URI generation and management — lazy, atomic, immutable."""

import logging
import string
import secrets

from django.conf import settings
from django.db import transaction

from issuer.models import Document

logger = logging.getLogger("issuer")

DOC_ID_LENGTH = 10
DOC_ID_ALPHABET = string.ascii_uppercase + string.digits


def _generate_random_doc_id(length: int = DOC_ID_LENGTH) -> str:
    """Generate a cryptographically random alphanumeric doc_id."""
    return "".join(secrets.choice(DOC_ID_ALPHABET) for _ in range(length))


def build_uri(doc_type: str, doc_id: str) -> str:
    """Build a DLTS-compliant URI: <IssuerId>-<DocType>-<DocId>."""
    return f"{settings.DIGILOCKER_ISSUER_ID}-{doc_type}-{doc_id}"


def ensure_uri(document_id: int) -> str:
    """Lazily generate and persist a URI for the given document.

    Uses SELECT ... FOR UPDATE to guarantee exactly-once assignment
    under concurrent requests.
    """
    with transaction.atomic():
        doc = Document.objects.select_for_update().get(pk=document_id)

        if doc.uri:
            return doc.uri

        # Generate a unique doc_id — retry on collision (extremely unlikely)
        for _ in range(5):
            new_doc_id = _generate_random_doc_id()
            if not Document.objects.filter(doc_id=new_doc_id).exists():
                break
        else:
            raise RuntimeError("Failed to generate unique doc_id after retries")

        doc.doc_id = new_doc_id
        doc.uri = build_uri(doc.document_type, new_doc_id)
        doc.save(update_fields=["doc_id", "uri", "updated_at"])

        logger.info("Generated URI %s for document %d", doc.uri, doc.pk)
        return doc.uri
