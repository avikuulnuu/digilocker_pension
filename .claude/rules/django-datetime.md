---
paths:
  - "**/*.py"
---

# Datetime discipline

The project uses `USE_TZ = True` and `TIME_ZONE = "Asia/Kolkata"`.

- Use `django.utils.timezone.now()` for current timestamps.
- Pass `timezone.now` as a model-field default; do not call it at import time.
- Reject or normalize ambiguous external timestamps before comparing them with aware datetimes.
- Do not introduce `datetime.now()`, `datetime.utcnow()`, or stored formatted strings for values used as dates.
- Preserve DigiLocker timestamp text when required by the protocol, but use aware datetime objects for validation and arithmetic.
