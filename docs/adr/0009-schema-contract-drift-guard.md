# ADR 0009 — Pydantic↔ORM drift guard instead of generated ORM

**Status:** Accepted

## Context
The Bronze field set is declared twice: as Pydantic schemas (validation contract) and as
SQLAlchemy ORM models (DB DDL, Alembic-managed). The reusability audit proposed **generating**
the ORM from Pydantic to remove this duplication.

## Decision
Keep both declarations, but **enforce their consistency** with a contract test
(`tests/test_contracts.py`): the ORM data columns must equal the contract's fields, and optional
contract fields must map to nullable columns. The Pydantic schemas are versioned
(`CONTRACT_VERSION`) and their `parse_reason` behaviour is pinned per source. **No dynamic ORM
generation.**

## Consequences
- The real risk of the duplication — silent **drift** — is caught by CI; a renamed/added/removed
  field fails the test immediately.
- We avoid fighting Alembic: the ORM carries specific column types/lengths (`VARCHAR(32)`, `time`
  as `String(16)`, `DateTime(timezone=True)`) that Pydantic doesn't express; generating would
  change the DB schema (a migration) for little benefit and some risk (e.g. `time`/`date`
  semantics on ingest).
- If lengths/types later move into Pydantic (`Field(max_length=…)`), full generation can be
  revisited — the guard test would then validate the generated output.
