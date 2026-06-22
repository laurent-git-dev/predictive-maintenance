---
name: run-pipeline
description: Run the full medallion pipeline (Bronze→Silver→Gold + cross-source) and summarise the run. Use when the user wants to (re)generate a pipeline run or a reference run. Handles Docker/DB and the corporate proxy, then reports rows per layer and lineage.
---

# Run the full pipeline

Encodes RUNBOOK §0–1. The pipeline is idempotent (tables/artefacts replaced).

## Preflight

- Run from the project root.
- `.env` must exist with at least `ANONYMIZATION_SALT` (else `cp .env.example .env` and fill it).
- **Database (optional)** — `docker compose up -d` starts PostgreSQL so the DB-load step runs.
  If it is down, that step is **skipped with a warning**; Bronze/Silver/Gold still run on files.
- **Corporate proxy (Avast TLS)** — only matters for *network* `uv`/`dvc` ops: add `--native-tls`
  (or `UV_SYSTEM_CERTS=true`). The pipeline itself needs no network.

## Run

```bash
uv run python scripts/run_pipeline.py
# file-only (no database):
uv run python scripts/run_pipeline.py --no-db
```

A single source (Bronze + Silver) only:
```bash
uv run python scripts/run_{incidents,telemetry,machines,cross_source}.py [--no-db]
```

## Summarise (report back to the user)

- New timestamped folders `YYYYMMDDHHMM` under `artifacts/ingestions/<source>/<run>/{bronze,silver}/`
  and `artifacts/analyses/cross_source/<run>/`; each `runs_registry.json` updated.
- Report **rows per layer** (Bronze/Silver per source, Gold = machine-hours) from the run logs
  or `runs_registry.json`.
- If the DB ran, show the batch lineage: `uv run python -c "from src.framework.db.engine import
  get_engine; from src.framework.lineage.tracker import lineage_markdown; print(lineage_markdown(get_engine()))"`
  (one row per step in `meta.processing_runs`, with status / rows / quality_ok / output_hash).

To version + commit the produced run, use the `commit-run` skill.
