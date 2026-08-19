---
name: testing
description: "Write, review, or run automated tests for this DigiLocker Issuer Django application. Use when changing authentication, XML parsing or responses, document retrieval, identity validation, URI generation, file integrity, logging, IP allowlists, management portal security, models, or migrations."
---

# Testing the DigiLocker Issuer

Use Django's built-in test runner and `django.test.TestCase`; do not add pytest unless explicitly requested. Tests live under `tests/` and should follow the nearest existing module.

## Priority

1. Authentication: valid and invalid HMAC/KeyHash, missing headers, organization mismatch, and timestamp behavior when enabled.
2. XML protocol: valid parsing, malformed XML, required attributes, UDF extraction, success/error response schema, and escaping.
3. Retrieval: document found/not found, type mismatch, inactive records, and expected exception reason codes.
4. Identity: normalization, STRICT exact matching, LENIENT threshold boundaries, and safe failure handling.
5. URI and persistence: idempotent assignment, paired ID/URI constraints, locking intent, access counts, and audit rows.
6. Files and integrity: storage-root resolution, unavailable files, checksums, and STRICT/WARN/OFF behavior using temporary directories.
7. Portal and infrastructure: permission gates, login security, IP allowlists, read-only admin, filters, file preview, and safe logging.

## Conventions

- Name tests `test_<condition>_<expected_result>` and assert one behavior per method.
- Use `override_settings` for modes, secrets, issuer IDs, allowlists, and storage roots.
- Use `tempfile` for file tests and `unittest.mock.patch` at the call site for external or nondeterministic boundaries.
- Build the smallest model fixture needed; do not depend on `seed_documents` having run.
- Assert observable outputs: status code, XML, exception type/reason, database state, log redaction, or permission result.
- Never place real secrets or personal identifiers in fixtures or failure messages.
- Use `TransactionTestCase` only when a test truly requires transaction or locking behavior.

## Commands

```text
python manage.py test tests.test_authentication
python manage.py test tests.test_views.PullURIViewTest
python manage.py test tests.test_file_service tests.test_uri_service
python manage.py test
```

After model changes, also run:

```text
python manage.py makemigrations --check
```