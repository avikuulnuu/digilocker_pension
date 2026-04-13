"""File storage resolution and integrity checking."""

import hashlib
import logging
import os

from django.conf import settings
from django.utils import timezone

from issuer.models import Document, IntegrityLog

logger = logging.getLogger("issuer")

CHUNK_SIZE = 8192


class FileNotAvailableError(Exception):
    pass


class IntegrityCheckError(Exception):
    pass


def resolve_path(doc: Document) -> str:
    """Resolve absolute path from base config + relative path."""
    return os.path.join(settings.DIGILOCKER_BASE_STORAGE_PATH, doc.file_relative_path)


def compute_checksum(file_path: str) -> str:
    """Compute SHA-256 hex digest of a file."""
    sha = hashlib.sha256()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            sha.update(chunk)
    return sha.hexdigest()


def read_file_bytes(doc: Document) -> bytes:
    """Read document file, performing integrity checks per configured mode.

    Returns file content bytes on success.
    Raises FileNotAvailableError or IntegrityCheckError in STRICT mode.
    """
    full_path = resolve_path(doc)
    mode = settings.DIGILOCKER_INTEGRITY_MODE

    # Check existence
    if not os.path.isfile(full_path):
        _log_integrity(doc, full_path, "FILE_MISSING", "", "", mode)
        raise FileNotAvailableError(f"File not found: {doc.file_relative_path}")

    # Check size limit
    file_size = os.path.getsize(full_path)
    max_bytes = settings.DIGILOCKER_MAX_FILE_SIZE_MB * 1024 * 1024
    if file_size > max_bytes:
        raise FileNotAvailableError(
            f"File exceeds {settings.DIGILOCKER_MAX_FILE_SIZE_MB}MB limit"
        )

    # Read content
    with open(full_path, "rb") as f:
        content = f.read()

    # Integrity check
    if doc.file_checksum:
        calculated = compute_checksum(full_path)
        if calculated != doc.file_checksum:
            action = _log_integrity(
                doc, full_path, "CHECKSUM_MISMATCH",
                doc.file_checksum, calculated, mode,
            )
            if mode == "STRICT":
                raise IntegrityCheckError("Document integrity check failed")

    # Update last-checked timestamp
    doc.file_last_checked_at = timezone.now()
    doc.file_size_bytes = file_size
    doc.save(update_fields=["file_last_checked_at", "file_size_bytes"])

    return content


def _log_integrity(doc, file_path, issue_type, stored, calculated, mode):
    """Record an integrity issue and return the action taken."""
    action = "BLOCKED" if mode == "STRICT" else "SERVED"
    IntegrityLog.objects.create(
        document=doc,
        issue_type=issue_type,
        stored_checksum=stored,
        calculated_checksum=calculated,
        file_path=file_path,
        action_taken=action,
    )
    logger.warning(
        "Integrity issue: %s for doc %d at %s (action=%s)",
        issue_type, doc.pk, file_path, action,
    )
    return action
