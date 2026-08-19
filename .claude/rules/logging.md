---
paths:
  - "**/*.py"
---

# Logging discipline

- Follow the existing application convention `logging.getLogger("issuer")` in issuer code. Use module loggers only where the surrounding module already does so.
- Prefer the structured event helpers in `issuer.services.pull_doc_log` for Pull URI request lifecycle events.
- Apply `issuer.log_safety` helpers before logging identifiers. Never log raw XML bodies, response documents, HMAC/KeyHash values, API keys, names, mobile numbers, authorization numbers, DigiLocker IDs, identity match details, or full file paths.
- Use lazy `%s` arguments instead of f-strings in logging calls.
- Include `exc_info=True` for unexpected exceptions. Keep expected authentication and protocol failures concise and free of sensitive context.
- Use `self.stdout.write` for management-command output; do not use `print()` in application code.