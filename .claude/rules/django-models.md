---
paths:
  - "issuer/models.py"
---

# Model conventions

- Keep persistence shape, constraints, indexes, and small display helpers in models; retrieval and protocol workflows belong in services.
- Preserve `Document` uniqueness on `(authorization_number, document_type)` and the paired URI/ID, non-negative access count, and positive file-size constraints.
- Add indexes only for demonstrated lookup, filtering, ordering, or reporting paths; avoid redundant indexes.
- Use `DecimalField` for monetary values and `settings.AUTH_USER_MODEL` for user relations.
- Use `auto_now_add`, `auto_now`, or the callable `timezone.now` for timestamps.
- Every model change requires a migration and targeted constraint/model tests.
