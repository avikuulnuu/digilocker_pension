---
name: digi-documentation
description: "Write or update documentation for this DigiLocker Issuer application. Use for architecture notes, API compliance documentation, setup or operations guidance, Postman instructions, management portal guidance, or documentation of issuer behavior and configuration."
---

# DigiLocker Issuer documentation

Base every statement on current code, settings, tests, or the governing specification. Do not invent apps, roles, endpoints, commands, or documentation folders.

## Choose the destination

| Content | Location |
|---|---|
| Setup, configuration, commands, deployment overview | `README.md` |
| Architecture, schema, protocol design, compliance plan | `architecture/` |
| Postman collection usage and test data | `postman_automation/README.txt` |
| Detailed operator or user material explicitly requested by the user | `data/docs/` |

Keep specifications and historical design documents intact unless the request explicitly asks to revise them. For implementation status, distinguish clearly between specification requirements, current behavior, and planned work.

## Workflow

1. Read the relevant implementation, settings, tests, and existing document.
2. Identify the intended audience and source of truth.
3. Use exact endpoint names, settings, model fields, commands, and observed UI labels.
4. Document security-sensitive configuration by variable name only; never include real keys, credentials, identifiers, or filesystem secrets.
5. Add concise validation or troubleshooting steps using commands that exist in this repository.
6. Check links, paths, headings, and examples against the workspace before finishing.

For API behavior, consult `architecture/Digital Locker Issuer API Specification v1.13.md`. For database behavior, consult `issuer/models.py` and the migrations rather than relying only on the older design document.
