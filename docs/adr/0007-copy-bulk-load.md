# ADR 0007 — Bulk-load tables via PostgreSQL COPY

**Status:** Accepted

## Context
The default `DataFrame.to_sql` (row-by-row INSERT) took ~5 min for the wide Gold table
(≈216 cols × 134k rows).

## Decision
`write_table` loads via a **PostgreSQL `COPY`** pandas `to_sql` method (DDL still created from
dtypes; only the data load changes). NaN/None map to SQL `NULL` and empty strings (`""`) are
preserved via a distinct null marker (`\N`).

## Consequences
- Benchmarked **×3.2** vs default (40k×216: 134.6s → 42.3s), gap widening with row count.
- `method="multi"` was measured **slower** for wide tables (param-bloated multi-VALUES) and
  rejected — a reminder to **measure, not assume**.
- COPY is PostgreSQL-specific; `write_table` is only used for the medallion DB, so this is fine.
- Correctness (NULL vs `""`, NaN→NULL, types) covered by a DB round-trip test that skips without
  a database (so CI, which has no DB, stays green).
