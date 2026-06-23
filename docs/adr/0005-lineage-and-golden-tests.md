# ADR 0005 — Lineage table + golden tests via output hash

**Status:** Accepted

## Context
A 6000-LOC pipeline needs (a) run traceability and (b) a safety net before refactoring.

## Decision
Every `run_pipeline` opens a **batch** (`batch_id`); each step writes one row to
**`meta.processing_runs`** (layer, source, in/out refs, timings, status, rows
read/ingested/rejected, `quality_ok`, git `code_version`, and a deterministic **`output_hash`**
of the produced frame). The same content hash powers **golden tests**: Bronze/Silver row counts +
Silver/Gold content hashes are frozen, so any refactor that changes a result is caught
immediately. Unit tests cover the processing tools, validation, reject policy and Gold builder.

## Consequences
- Full lineage per run (`WHERE batch_id = X`); soft quality checks logged, non-blocking.
- Refactors (B1/B2/B3/B4/perf) were all proven behaviour-neutral by the golden hashes.
- Golden tests need `data/raw` → they skip in CI; CI runs the unit subset (`-m "not golden"`).
