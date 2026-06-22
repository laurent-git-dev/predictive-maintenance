---
name: add-source
description: Scaffold a new medallion data source end-to-end (Bronze + Silver, contributing to Gold). Use when the user wants to add/onboard a new data source to the pipeline. Does the whole ARCHITECTURE checklist at once, reusing src/framework and mirroring existing sources.
---

# Add a new data source

Permanent instruction (CLAUDE.md): do the **whole checklist in one pass**, reusing
`src/framework/` and mirroring an existing source (the runner stays **thin**). Mapping facts
(table/keys/model/role) live in **one place**: the source runner → aggregated into `SourceSpec`.
Detail: [docs/ARCHITECTURE.md → "Add a new source"](../../../docs/ARCHITECTURE.md).

Ask the user for: source **name**, raw input (file/SQL), columns + types + domains, duplicate
key(s), and whether it feeds Gold (and as which slot: `incidents`/`telemetry`/`maintenance`).

## Steps

1. **Kernel config** — in `src/config.py`: schema/table name, raw path, column-name constants.
   Any quality criteria go in `src/quality.py` (`FEATURE_CHECKS` / reusable `Check`s).
2. **Source package** `src/usecase/sources/<name>/`:
   - `loader.py` — `load_<name>()`: raw typed load, **no treatment** (pseudonymise operators only if PII).
   - `runner.py` (**thin**) exposing: `SOURCE_NAME`, `TABLE`, `MODEL` (Pydantic), `DUP_KEYS`,
     `RAW_REF` (datalake file), `GOLD_ROLE` (or omit if Bronze-only), `BRONZE_NUMERIC`,
     `SILVER_NUMERIC`, `load_bronze()`, `to_silver(bronze_df) -> (df, report)` via
     `apply_processing(...)`. Optional hooks read by the registry: `COUNT_FEATURES`,
     `COUNT_LABEL`, `KEYWORD_BARS`, `HEATMAPS`, `TIMESERIES`, `OVERVIEW`, `FEATURE_PLOTS`,
     `MACHINE_COL`, `CUMULATIVE`, `BARS_BY_MACHINE`, `PROCESSING`, `BRONZE_ONLY`.
3. **Schema & ORM** — Pydantic row model in `src/usecase/ingestion/schemas.py`; Bronze ORM in
   `src/usecase/db/models_bronze.py`; add an Alembic migration (`uv run alembic revision -m ...`).
4. **Register** — add `_spec(<name>_runner)` to `SOURCE_SPECS` in
   `src/usecase/sources/registry.py`. The orchestrator then handles Bronze + Silver + DB load.
5. **Gold** — there is **no per-source `to_gold`**: if it feeds Gold, set `GOLD_ROLE` and extend
   the unified builder in `src/usecase/gold/features.py`.
6. **CLI** — `scripts/run_<name>.py` (mirror an existing one: `run_source_by_name("<name>")`,
   Agg backend, `--no-db`).
7. **Notebook** — add the source under chapters 1/2 using helpers from
   `src.usecase.notebook.render`.
8. **Tests** — add unit coverage; if it feeds Gold, add its row-count/hash to `tests/test_golden.py`.
9. **Document** — `CLAUDE.md`, `README.md`, `docs/ARCHITECTURE.md`.

## Finish

Run the `quality-gate` skill (or `uv run ruff check src scripts tests conftest.py` +
`uv run black src ...` + `uv run pytest -q`). Then a quick `uv run python scripts/run_<name>.py
--no-db` to smoke-test. Commit with a Conventional Commit (`feat(<name>): ...`).
