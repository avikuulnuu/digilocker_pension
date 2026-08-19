# DigiLocker Issuer core invariants

Apply these rules to every change in this repository.

## Architecture

- Preserve the dependency direction: views call services; services use models and infrastructure helpers. Models never depend on HTTP concerns.
- Keep `issuer/views.py` focused on XML/HTTP orchestration and `issuer/manage_views.py` focused on portal request handling.
- Put document lookup, identity validation, URI assignment, file integrity, XML parsing, and response construction in the existing `issuer/services/` modules.
- Do not introduce DRF, Celery, or a SPA unless explicitly requested.

## API security and protocol

- Authenticate DigiLocker API requests through `issuer.authentication.authenticate_request`; preserve constant-time HMAC and KeyHash comparisons.
- Keep raw request bodies, HMAC values, API keys, identity details, mobile numbers, authorization numbers, DigiLocker IDs, and file paths out of logs.
- Build API XML only through `issuer.services.response_builder`; preserve the DigiLocker Issuer API v1.13 response schema and HTTP status behavior.
- Treat `AuthenticationError` as HTTP 401. Translate expected document, identity, file, and integrity failures into protocol XML responses. Log unexpected failures with traceback and return HTTP 500.

## Data integrity

- Generate a document URI only through `issuer.services.uri_service.ensure_uri`; preserve its atomic transaction and `select_for_update()` locking.
- Preserve the invariant that `digilocker_doc_id` and `digilocker_uri` are either both set or both null.
- Respect `IDENTITY_VALIDATION_MODE` and `INTEGRITY_MODE`; do not weaken STRICT behavior as a fallback.
- Keep Django admin read-only for issuer records. Management portal views require login and the `issuer.access_manage_portal` permission.
- Use timezone-aware datetimes via `django.utils.timezone`.

## Validation

- Run the narrowest relevant `python manage.py test tests.<module>` after a change, then broader tests when shared API behavior is affected.
- Include a migration for model changes and run `python manage.py makemigrations --check`.