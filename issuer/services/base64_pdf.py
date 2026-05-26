"""Decode Base64 strings into PDF bytes for the manage portal tool."""

import base64
import re

import binascii


def normalize_base64_input(raw: str) -> str:
    """Strip whitespace and optional data-URI prefix."""
    text = (raw or "").strip()
    if "," in text and "base64" in text[:80].lower():
        text = text.split(",", 1)[1]
    return re.sub(r"\s+", "", text)


def decode_pdf_bytes(raw: str, *, max_bytes: int) -> bytes:
    """
    Decode a Base64-encoded PDF.

    Raises ValueError with a user-facing message on failure.
    """
    b64 = normalize_base64_input(raw)
    if not b64:
        raise ValueError("Paste a Base64-encoded PDF string.")

    try:
        data = base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Invalid Base64 encoding.") from exc

    if not data.startswith(b"%PDF"):
        raise ValueError("Decoded data is not a PDF (missing %PDF header).")

    if len(data) > max_bytes:
        limit_mb = max(1, max_bytes // (1024 * 1024))
        raise ValueError(f"PDF exceeds the {limit_mb} MB size limit.")

    return data
