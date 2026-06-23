# ADR 0003 — Silver reject policy (correctable vs rejected)

**Status:** Accepted

## Context
Silver reads the flagged `bronze.*` rows. It must decide which flagged rows to keep and clean,
and which to drop.

## Decision
A flagged row is **kept and corrected** when its only anomalies are **correctable by a
treatment**: `duplicate` (→ deduplication) or `missing` (→ imputation / time interpolation).
A row carrying any **non-correctable** anomaly (`type` / `domain` / `format` / `range` /
`invalid`) is **rejected** (dropped). The parse columns are then dropped from the kept frame
before treatments. See `split_rejected` in `src/usecase/silver/refine.py`.

## Consequences
- Treatments only ever face anomalies they can actually fix; rejected rows are counted and
  their reasons reported (no silent data loss).
- The policy is centralised in one function and unit-tested (`tests/test_refine_policy.py`).
- Adding a new correctable anomaly = extend the `CORRECTABLE` set + the matching treatment.
