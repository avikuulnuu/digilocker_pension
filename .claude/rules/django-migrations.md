---
paths:
  - "issuer/migrations/**/*.py"
---

# Migration conventions

- Keep each migration focused on one coherent schema or data change and give it a descriptive name.
- Preserve production data. Use staged nullable/backfill/constraint changes when adding required fields to populated tables.
- Keep PostgreSQL-specific indexes, constraints, and triggers compatible with the existing migration history.
- Never edit an applied migration unless explicitly handling an unreleased migration; add a new migration instead.
- Validate with `python manage.py makemigrations --check`, the relevant tests, and `python manage.py migrate` when a database is available.
