"""File storage resolution and integrity checking."""

import hashlib
import logging
import os

from django.conf import settings
from django.utils import timezone

from issuer.models import Document, IntegrityLog
from issuer.services.pull_doc_log import stage_failed, stage_ok

logger = logging.getLogger("issuer")

CHUNK_SIZE = 8192


class FileNotAvailableError(Exception):
    pass


class IntegrityCheckError(Exception):
    pass


def _storage_base() -> str:
    return (settings.DIGILOCKER_BASE_STORAGE_PATH or "").rstrip("/\\")


def _normalize_file_name(file_name: str) -> str:
    """Strip whitespace; use relative path under storage base only."""
    name = (file_name or "").strip().replace("\\", "/")
    while name.startswith("./"):
        name = name[2:]
    return name.lstrip("/")


def effective_file_name(file_name: str) -> str:
    """Return file_name with .pdf appended when no extension is present."""
    name = _normalize_file_name(file_name)
    if not name:
        return ""
    if not os.path.splitext(name)[1]:
        return f"{name}.pdf"
    return name


def candidate_paths(doc: Document) -> list[str]:
    """Absolute paths to try for this document (prefers .pdf when extension omitted)."""
    base = _storage_base()
    raw = _normalize_file_name(doc.file_name)
    if not base or not raw:
        return []

    effective = effective_file_name(doc.file_name)
    paths = [os.path.join(base, effective)]
    if effective != raw:
        paths.append(os.path.join(base, raw))
        paths.append(os.path.join(base, f"{raw}.PDF"))

    seen = set()
    unique = []
    for path in paths:
        if path not in seen:
            seen.add(path)
            unique.append(path)
    return unique


def resolve_path(doc: Document) -> str:
    """Primary expected absolute path (uses effective_file_name)."""
    base = _storage_base()
    name = effective_file_name(doc.file_name)
    if not base or not name:
        return os.path.join(base or "", name or "")
    return os.path.join(base, name)


def find_readable_path(doc: Document) -> str | None:
    """Return the first candidate path that exists and is readable, or None."""
    for path in candidate_paths(doc):
        if os.path.isfile(path) and os.access(path, os.R_OK):
            return path
    return None


def diagnose_document_file(doc: Document) -> dict:
    """Build diagnostics for manage UI / staging troubleshooting."""
    base = _storage_base()
    name = _normalize_file_name(doc.file_name)
    effective = effective_file_name(doc.file_name)
    candidates = []
    for path in candidate_paths(doc):
        exists = os.path.exists(path)
        candidates.append({
            "path": path,
            "exists": exists,
            "is_file": os.path.isfile(path),
            "readable": os.access(path, os.R_OK) if exists else False,
        })

    matching = []
    list_error = ""
    if base and name and os.path.isdir(base):
        try:
            prefixes = {os.path.basename(name), os.path.basename(effective)}
            for entry in sorted(os.listdir(base)):
                if entry in prefixes or any(entry.startswith(p) for p in prefixes):
                    matching.append(entry)
                if len(matching) >= 15:
                    break
        except OSError as exc:
            list_error = str(exc)
    elif base and not os.path.isdir(base):
        list_error = "BASE_STORAGE_PATH is not a directory from this process"

    return {
        "base_storage_path": base,
        "base_is_dir": os.path.isdir(base) if base else False,
        "base_readable": os.access(base, os.R_OK) if base and os.path.isdir(base) else False,
        "normalized_file_name": name,
        "effective_file_name": effective,
        "candidates": candidates,
        "matching_entries": matching,
        "list_error": list_error,
        "resolved_path": find_readable_path(doc),
    }


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


def read_file_bytes(doc: Document, *, request_ip=None, digilocker_txn=None, digilocker_id=None) -> bytes:
    """Read document file, performing integrity checks per configured mode.

    Returns file content bytes on success.
    Raises FileNotAvailableError or IntegrityCheckError in STRICT mode.
    """
    full_path = find_readable_path(doc)
    mode = settings.DIGILOCKER_INTEGRITY_MODE

    # Check existence
    if not full_path:
        expected = resolve_path(doc)
        tried = ", ".join(candidate_paths(doc))
        stage_failed(
            "file_read",
            f"File not found on disk: {doc.file_name}",
            document_id=doc.pk,
            path=expected,
            tried_paths=tried,
            digilocker_txn=digilocker_txn,
        )
        _log_integrity(
            doc, expected, "FILE_MISSING", "", "", mode,
            extra_context={
                "request_ip": request_ip,
                "digilocker_txn": digilocker_txn,
                "digilocker_id": digilocker_id,
            }
        )
        raise FileNotAvailableError(f"File not found: {doc.file_name}")

    # Check size limit
    file_size = os.path.getsize(full_path)
    max_bytes = settings.DIGILOCKER_MAX_FILE_SIZE_MB * 1024 * 1024
    if file_size > max_bytes:
        stage_failed(
            "file_read",
            f"File exceeds {settings.DIGILOCKER_MAX_FILE_SIZE_MB}MB limit",
            document_id=doc.pk,
            file_size=file_size,
            max_bytes=max_bytes,
        )
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
                extra_context={
                    "stored_file_size": file_size,
                    "calculated_file_size": file_size,
                    "request_ip": request_ip,
                    "digilocker_txn": digilocker_txn,
                    "digilocker_id": digilocker_id,
                }
            )
            stage_failed(
                "integrity",
                "Checksum mismatch",
                document_id=doc.pk,
                stored=doc.file_checksum,
                calculated=calculated,
                action=action,
                mode=mode,
            )
            if mode == "STRICT":
                raise IntegrityCheckError("Document integrity check failed")

    # Update last-checked timestamp
    doc.file_last_checked_at = timezone.now()
    doc.file_size_bytes = file_size
    doc.save(update_fields=["file_last_checked_at", "file_size_bytes"])

    stage_ok(
        "file_read",
        "File read and verified",
        document_id=doc.pk,
        file_name=doc.file_name,
        file_size=file_size,
        digilocker_txn=digilocker_txn,
    )
    return content


def _log_integrity(doc, file_path, issue_type, stored, calculated, mode, extra_context=None):
    """Record an integrity issue and return the action taken."""
    action = "BLOCKED" if mode == "STRICT" else "SERVED"
    extra = extra_context or {}
    IntegrityLog.objects.create(
        document=doc,
        issue_type=issue_type,
        stored_checksum=stored,
        calculated_checksum=calculated,
        file_path=file_path,
        action_taken=action,
        authorization_number=getattr(doc, "authorization_number", ""),
        document_type=getattr(doc, "document_type", ""),
        stored_file_size=extra.get("stored_file_size"),
        calculated_file_size=extra.get("calculated_file_size"),
        request_ip=extra.get("request_ip", ""),
        digilocker_txn=extra.get("digilocker_txn", ""),
        digilocker_id=extra.get("digilocker_id", ""),
    )
    logger.warning(
        "Integrity issue: %s for doc %d at %s (action=%s)",
        issue_type, doc.pk, file_path, action,
    )
    return action
