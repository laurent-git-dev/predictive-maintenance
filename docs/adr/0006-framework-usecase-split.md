# ADR 0006 — Framework / use-case split + shared kernel

**Status:** Accepted

## Context
Generic medallion plumbing (layer staging, profiling, validation engine, lineage, DB engine)
was mixed with the predictive-maintenance specifics (4 sources, schemas, Gold spec). Goal:
make the engine reusable for other use cases.

## Decision
Three tiers under `src/`, with a strictly enforced dependency rule **kernel ← framework ←
usecase**:
- **kernel** (`config.py`, `quality.py`): passive project configuration; depends on nothing.
- **`framework/`**: generic engine (`common`, `processing`, `ingestion` validate/stats,
  `lineage`, `db`). May import the kernel only — **never** `src.usecase.*`.
- **`usecase/`**: this application (sources+registry, schemas, Bronze ORM, silver, gold,
  analyses, orchestrator, notebook). Free to import framework + kernel.

## Consequences
- The boundary is materialised and import-enforced (a stray `framework → usecase` import is a bug).
- A new use case reuses `framework/` as-is and adds its own `usecase`-style package.
- `config.py`/`quality.py` stay shared (kernel) rather than parameterising every engine call —
  a pragmatic limit accepted to bound the refactor.
