# ADR 0001 — Medallion layers chained through PostgreSQL

**Status:** Accepted

## Context
The pipeline has Bronze / Silver / Gold layers. Layers could pass data in memory, via files, or
via a database.

## Decision
Each layer reads the previous one **from PostgreSQL**: `data/raw/` → `bronze.*` → `silver.*` →
`gold.features`. Silver reads `bronze.*`, Gold reads `silver.*`. A `--no-db` fallback keeps the
pipeline runnable on files when no database is available.

## Consequences
- Clear, inspectable contracts between layers; each layer is independently queryable/restartable.
- The "source of truth" between layers is the DB, not intermediate files — so a file-dependency
  DAG (e.g. DVC `dvc.yaml`) is a poor fit (see [0008](0008-gold-params-no-dvc-dag.md)).
- Requires a running PostgreSQL for the full path; the `--no-db` mode trades fidelity for
  availability (Silver then reads the in-memory Bronze frame).
