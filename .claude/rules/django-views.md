---
paths:
  - "issuer/views.py"
  - "issuer/manage_*.py"
---

# View conventions

- Keep API orchestration in `issuer/views.py`: read the body and headers, parse XML, authenticate, call services, and return the response.
- Keep management portal concerns in `issuer/manage_views.py`; use the helpers in `manage_auth.py`, `manage_filters.py`, and `manage_forms.py` rather than duplicating them.
- Protect portal views with login and the `issuer.access_manage_portal` permission. Preserve POST-redirect-GET for portal mutations.
- Build DigiLocker XML with `issuer.services.response_builder`; do not construct protocol XML inline.
- Preserve exception mapping: authentication failures return HTTP 401, expected retrieval failures return protocol XML, and unexpected failures return HTTP 500 after safe traceback logging.
- Record access attempts consistently, including expected failure paths. Do not let audit/logging enrichment expose sensitive values.
- Paginate growing portal querysets and use `select_related()`/`prefetch_related()` when rendering related data.
