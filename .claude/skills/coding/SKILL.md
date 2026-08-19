---
name: coding
description: "Review or critique DigiLocker Issuer code for architecture, correctness, performance, security, logging, and maintainability. Use when evaluating code quality, a diff, or a pull request at a general engineering level."
---

# Coding review

Use a principal-engineer review lens. Lead with actionable findings ordered by severity and cite exact files and lines. Do not rubber-stamp or spend the response summarizing code.

## Review dimensions

1. **Correctness:** Trace success, expected failure, malformed input, and concurrency paths. Check model constraints and transaction boundaries.
2. **Architecture:** Preserve views to services to models. Keep XML parsing/building, authentication, document retrieval, identity validation, URI generation, and file integrity in their owning modules.
3. **Security:** Check authentication, permissions, constant-time comparisons, input parsing, sensitive-data handling, path safety, and error disclosure.
4. **Protocol compliance:** Compare Pull URI behavior with `architecture/Digital Locker Issuer API Specification v1.13.md` and existing response tests.
5. **Data integrity:** Check uniqueness, paired URI fields, access counts, checksums, atomic URI assignment, and migration safety.
6. **Observability:** Require useful event logging without raw XML, secrets, identity details, identifiers, or paths.
7. **Performance:** Look for repeated file reads, N+1 queries, unbounded portal queries, and avoidable hashing or XML work.
8. **Tests:** Require focused regression coverage for changed behavior and both accepted and rejected paths.

For DigiLocker-specific checks, also use the `digi-code-review` skill. The canonical implementation rules are under `.claude/rules/`.
