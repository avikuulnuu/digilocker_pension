"""Template context for issuer management UI."""

from issuer.manage_decode_pdf import manage_decode_pdf_enabled


def manage_portal(request):
    return {
        "manage_decode_pdf_enabled": manage_decode_pdf_enabled(),
    }
