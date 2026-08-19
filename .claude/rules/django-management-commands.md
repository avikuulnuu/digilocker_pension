---
paths:
  - "issuer/management/commands/**/*.py"
---

# Management command conventions

- Keep commands idempotent where practical and validate inputs before writing.
- Use `self.stdout.write` and `self.stderr.write`, never `print()`.
- Keep reusable document import, validation, and account-provisioning logic outside the command class when it is also needed elsewhere.
- Never print passwords, API keys, raw identity data, authorization numbers, mobile numbers, or storage paths.
- Preserve the behavior and options of `seed_documents` and `create_manage_portal_user` unless a breaking change is explicitly requested.
