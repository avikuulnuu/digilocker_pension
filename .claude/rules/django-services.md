---
paths:
  - "issuer/services/**/*.py"
---

# Service conventions

- Keep one responsibility per module and extend the existing parser, validator, document, URI, file, response, and logging services before creating parallel implementations.
- Prefer plain inputs and return values. HTTP request and response objects belong in views; XML elements belong in parser/response modules.
- Raise the existing specific service exception for an expected failure. Do not collapse document-not-found, identity-mismatch, file-unavailable, and integrity-check failures into a generic exception.
- Keep multi-write and concurrency-sensitive operations atomic. URI assignment must retain `select_for_update()` and remain idempotent.
- Respect settings-driven STRICT, WARN, LENIENT, and OFF modes exactly; an invalid mode must fail safely rather than silently weaken validation.
- Search and update all call sites when changing a service signature or return shape.
