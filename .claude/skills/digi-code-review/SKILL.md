---
name: digi-code-review
description: "Review, debug, or assess changes to this DigiLocker Issuer API. Use for Pull URI XML, HMAC and KeyHash authentication, document lookup, identity matching, URI generation, file integrity, access auditing, management portal permissions, or Issuer API v1.13 compliance."
---

# DigiLocker Issuer code review

Review against the code and `architecture/Digital Locker Issuer API Specification v1.13.md`. Findings come first, ordered as blocker, should-fix, then suggestion. Include a concrete failure scenario and fix for each finding.

## Severity

- **Blocker:** exploitable security issue, authentication or authorization bypass, sensitive-data exposure, protocol breakage, data corruption, or unsafe migration.
- **Should-fix:** likely correctness, reliability, performance, or maintainability defect that can cause an incident or regression.
- **Suggestion:** localized improvement with low immediate risk. Do not present style preferences as defects.

## Domain invariants

| Area | Required behavior |
|---|---|
| Pull URI endpoint | `POST /api/pulluri`; parse and build XML through the existing services |
| Authentication | Verify HMAC-SHA256 and KeyHash with constant-time comparison; validate issuer organization ID |
| Document lookup | Resolve the authorization number and document type pair; reject inactive or unavailable records |
| Identity | Apply the configured STRICT or LENIENT name policy; do not leak match details |
| URI assignment | Assign lazily and exactly once inside an atomic `select_for_update()` path |
| File retrieval | Resolve only approved storage paths, read bytes safely, and apply STRICT/WARN/OFF integrity behavior |
| Audit | Record request outcomes and successful access counts consistently without sensitive payloads |
| Portal | Require login plus `issuer.access_manage_portal`; keep Django admin read-only |

## Trace the request

Read only the relevant path, generally in this order:

1. `issuer/views.py` and `issuer/authentication.py`
2. `issuer/services/xml_parser.py` and `response_builder.py`
3. `issuer/services/document_service.py` and `identity_validator.py`
4. `issuer/services/uri_service.py` and `file_service.py`
5. `issuer/services/pull_doc_log.py`, `issuer/log_safety.py`, and `issuer/models.py`
6. The matching module under `tests/`

For portal changes, inspect `issuer/manage_views.py`, `manage_auth.py`, `manage_filters.py`, `manage_forms.py`, `manage_login_security.py`, and the relevant templates.

## Good coding practices

- **Small, cohesive changes:** Each function and module should have one responsibility. Prefer the existing service boundary over duplicate helpers or speculative abstractions.
- **Clear contracts:** Use descriptive names, explicit inputs and return values, and specific exception types. Avoid hidden mutable state, broad `except Exception` handling for expected failures, and silent fallbacks.
- **Fail predictably:** Validate at system boundaries, reject invalid configuration values, preserve exception causes for diagnostics, and keep user-facing errors stable and non-sensitive.
- **Constants and configuration:** Reuse settings and established constants for protocol values, document types, limits, modes, and status codes. Do not scatter magic strings or environment-dependent paths.
- **Database discipline:** Keep related writes atomic, preserve locking where races are possible, avoid N+1 queries and unbounded lists, and enforce durable invariants with database constraints when practical.
- **Compatibility:** Check every caller when signatures, response shapes, model fields, URL names, settings, or templates change. Preserve the public API unless the change explicitly requires a break.
- **Readable implementation:** Prefer straightforward control flow, remove dead code and unused imports, and add comments only for non-obvious security, protocol, or concurrency decisions.
- **Testability:** Separate parsing, validation, persistence, and I/O so they can be tested independently. Require regression tests that fail without the proposed fix.

## Security review

### Authentication and request integrity

- Verify authentication occurs before document lookup, identity checks, file reads, or database mutation.
- Require constant-time comparison for HMAC, KeyHash, and other secrets; reject missing, malformed, or duplicate authentication inputs.
- Review timestamp freshness and replay protection. Flag disabled or bypassable timestamp validation unless the deployment has a documented compensating control.
- Fail closed when keys, issuer IDs, security modes, or required settings are absent or invalid. Never embed production secrets in code, tests, fixtures, or documentation.

### Input and XML handling

- Treat headers, XML attributes, UDF values, query parameters, form data, filenames, and imported records as untrusted.
- Use a hardened structured XML parser. Reject malformed XML, DTDs/external entities, excessive nesting, oversized bodies, and unexpected elements or attributes where the protocol requires a closed schema.
- Validate type, format, length, encoding, and allowed values before using input in queries, paths, logs, or responses. Preserve output escaping.

### Authorization and portal security

- Check authentication, `issuer.access_manage_portal`, and object-level restrictions on every portal action and file response; do not rely on hidden UI controls.
- Preserve CSRF protection for state-changing browser requests, secure redirect targets, session/login throttling, and restricted admin access.
- Ensure document downloads and previews use safe content types, disposition headers, and authorization checks without exposing server paths.

### Files, data, and privacy

- Resolve files under configured roots using canonical paths; reject traversal, symlink escape, arbitrary absolute paths, and user-controlled path joins.
- Verify integrity before serving in STRICT mode and preserve WARN/OFF semantics exactly. Avoid time-of-check/time-of-use gaps where practical.
- Minimize collected and returned data. Do not expose whether a sensitive identifier exists through unnecessary response, timing, or error differences.
- Review retention and write paths for `AccessLog`, `IntegrityLog`, access counts, and document metadata; audit records must not become a secondary sensitive-data store.

### Deployment and dependencies

- Review security-relevant Django settings when touched: `DEBUG`, `ALLOWED_HOSTS`, trusted origins, secure cookies, HTTPS redirect/proxy headers, HSTS, secret loading, and IP allowlists.
- Flag unsafe defaults that can reach production, overly broad hosts or networks, missing rate or body-size controls, and verbose production errors.
- Avoid new dependencies when the standard library or existing stack suffices. For added or upgraded packages, check maintenance status, version constraints, and known vulnerability exposure.

## Defects to flag

- Authentication performed after business processing, non-constant-time secret comparison, or authentication failures returned as normal XML success responses.
- Missing or ineffective replay protection without a documented compensating control.
- Raw XML, HMAC/KeyHash, API keys, names, mobile numbers, authorization numbers, DigiLocker IDs, identity details, or full paths in logs.
- Protocol XML assembled directly in a view, unsafe XML features enabled, or request size and structure left unbounded.
- URI assignment without the existing lock, or code that can overwrite an assigned URI/ID pair.
- STRICT identity or integrity failures downgraded to warnings or success.
- File paths accepted from request input, traversal or symlink escape, or resolution outside configured storage roots.
- Access count or audit rows updated inconsistently across success/failure branches.
- Portal access guarded only by login, missing CSRF/object authorization, unsafe redirects, or admin records made writable.
- Model changes without migrations or changes to shared behavior without focused tests.

## Validation

Run the narrowest relevant module, such as:

```text
python manage.py test tests.test_authentication
python manage.py test tests.test_views
python manage.py test tests.test_identity_validator
python manage.py test tests.test_uri_service
python manage.py test tests.test_manage_auth
```

Use `python manage.py test` when a change crosses authentication, retrieval, response, logging, or portal boundaries.
