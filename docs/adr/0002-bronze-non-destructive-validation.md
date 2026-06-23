# ADR 0002 — Bronze validates by flagging, never modifying

**Status:** Accepted

## Context
Raw rows can be invalid (bad type, out-of-domain, missing, duplicate). Bronze could clean/drop
them, or keep them. We want auditability of what arrived from the DataLake.

## Decision
Bronze ingests **every** row unchanged and adds two columns via Pydantic validation:
`parse_ok` (bool) and `parse_reason` (`;`-joined `kind:field` tokens — type / domain / range /
missing / format / duplicate). **No value is modified.** Tables are SQLAlchemy ORM, schema
managed by Alembic; a surrogate `id` PK is used because duplicates are kept (natural keys aren't
unique). Operator PII is the only exception — pseudonymised at ingestion (privacy gate).

## Consequences
- Full traceability: ingestion stats are exact ("what arrived, what's flagged and why").
- Cleaning is deferred to Silver, which decides what is correctable vs rejected
  (see [0003](0003-silver-reject-policy.md)).
- The flags are a stable contract consumed downstream; reason tokens are normalized.
