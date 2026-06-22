# Architecture

Detailed architecture of the predictive-maintenance medallion pipeline. `CLAUDE.md` keeps
the durable conventions and commands; this file is the map (read it on demand). The code in
`src/` is the ultimate source of truth.

## Layout

```
src/
├── config.py          chemins, schémas DB (BRONZE/SILVER/GOLD/META_SCHEMA), constantes
├── orchestrator.py    run_pipeline : Bronze+Silver par source → run_gold (1 table) → cross-source
├── common/            mutualisé : stage.run_layer, profiling (per-feature + plots + status),
│                      quality (OK/NOK), processing_summary, metrics, reporting, registry, overview, env
├── processing/        outils : anonymization, dedup, interpolation, transformation (encode),
│                      imputation, outliers, normalization, pipeline (apply_processing)
├── ingestion/         Bronze : schemas.py (Pydantic), validate.py (parse_ok/parse_reason),
│                      load.py (validate+flag+TRUNCATE/append), stats.py
├── silver/            refine.py : lit bronze.* (DB), reject policy, traitements → silver.* + stats
├── gold/              features.py (build_gold_features / build_gold_from_db) → gold.features ; stats.py
├── lineage/           models.py (meta.processing_runs), tracker.py (Batch+step), quality.py (soft)
├── database/          engine (ensure_schema), loader (to_sql par schéma), models_bronze.py (ORM)
├── sources/           1 package/source (runner mince) ; registry.py = SOURCE_SPECS
├── analyses/          analyses inter-sources (joins, plots, runner)
└── notebook/          render.py : helpers du notebook (importables) + état partagé
scripts/   run_pipeline.py (tout) + run_{incidents,telemetry,machines,cross_source}.py
notebooks/ pipeline.ipynb (3 chapitres BRONZE/SILVER/GOLD ; non DVC)
alembic/   migrations (0001 bronze, 0002 meta)
```

## Medallion flow (DB-chained)

Raw files (`data/raw/`) → **`bronze.*`** → **`silver.*`** → **`gold.features`**, each layer
reading the previous one **from the database**.

- **Bronze** — raw typed load (+ operator pseudonymisation). At ingestion, a **non-destructive
  Pydantic validation** adds `parse_ok` / `parse_reason` (type / domain / missing / duplicate),
  **without modifying values**; all rows are loaded into `bronze.*` (SQLAlchemy, schema managed
  by Alembic). 4 sources: `incidents`, `telemetry`, `machine` (dimension, Bronze-only),
  `machines` (maintenance facts).
- **Silver** — `src/silver/refine.py` reads `bronze.*`; **reject policy** (rows whose only
  anomalies are `duplicate`/`missing` are **kept & corrected** by the treatments; `type` /
  `domain` / `format` / `range` / `invalid` are **rejected**); then `apply_processing`
  (dedup, dimension merge, encode, impute, time interpolation, normalize) → `silver.*`
  (`to_sql` replace) + modification stats. 3 sources: `incidents`, `telemetry`, `maintenance`
  (the `machine` dimension is merged into `silver.maintenance` — star schema; no
  `silver.machine`). `to_silver` returns `(df, report)`; text→value maps traced in
  `…/silver/text_encodings.json`.
- **Gold** — **one cross-source table** `gold.features`, grain **(machine_id, 1h window)**,
  built from `silver.*` (`build_gold_from_db`). Use case: predict a **failure = incident of
  severity ≥ 4** at +6/12/24/48h. Decision instant **t = window_end**: features look back up
  to & including the current hour; labels look strictly after `t` (NaN if censored at the
  series end; row kept). Feature groups: **memory** (rolling mean/max/std), **trend** (OLS
  slope), **anomaly** (z-scores), **context** (incidents / signals / maintenance) and
  **labels** (4 horizons, multi-target). No leakage. Stats: `src/gold/stats.py`.

Everything generic is mutualised in `src/common/` (`stage.run_layer`, `profiling`, `quality`);
source runners are **thin** (`load_bronze`, `to_silver`, `BRONZE_NUMERIC`/`SILVER_NUMERIC` +
optional hooks). `to_sql` is `replace` per schema → idempotent.

## Database

| Schéma | Tables | Notes |
|---|---|---|
| `bronze` | `incidents`, `telemetry`, `machine`, `maintenance` | ORM + Alembic ; PK `id` ; `parse_ok`/`parse_reason` ; toutes lignes ingérées (invalides flaguées) |
| `silver` | `incidents`, `telemetry`, `maintenance` | `to_sql` replace ; `maintenance` enrichie de la dimension + `*_code` |
| `gold` | `features` | 1 table (machine, heure) |
| `meta` | `processing_runs` | lineage (cf. ci-dessous) |

Créer/mettre à jour le schéma : `uv run alembic upgrade head` (l'ingestion fait aussi un
`create_all` idempotent en filet de sécurité).

## Batch & traceability (lineage)

Chaque `run_pipeline` ouvre un **batch** (`batch_id`) ; chaque étape (ingest Bronze, refine
Silver, build Gold) écrit **une ligne** dans **`meta.processing_runs`** via
`src/lineage/tracker.py` (`Batch` + `batch.step(...)`) : `step`, `layer`, `source`,
`input_ref`/`output_ref`, `started_at`/`ended_at`/`duration_s`, `status`,
`rows_read`/`rows_ingested`/`rows_rejected`, `quality_ok`, `code_version` (git sha),
`output_hash`, `details` (JSON). Lignage complet : `SELECT … WHERE batch_id = X ORDER BY
started_at`. Contrôles qualité **soft** (`src/lineage/quality.py` : unicité du grain Gold,
continuité du nombre de lignes vs batch précédent) → enregistrés + warning, sans bloquer.

## Notebook (3 chapters)

`## 0. Setup` → `## 1. BRONZE (raw data)` → `## 2. SILVER (treated data)` → `## 3. GOLD
(ready for training)`. Each source follows the homogeneous template `### X.Y <Source>` →
`#### X.Y.1 PREVIEW` (per-feature understanding) → `#### X.Y.2 PROCESSING` (per-feature
transformation, **(NEW)** badge on created columns) → `#### X.Y.3 OVERVIEW` (Permanent +
Inline analysis). Cross-cutting content (DB upload, cross-source, synthesis, global overview,
batch lineage) sits in per-chapter **appendices**. Helpers live in `src/notebook/render.py`
(the Setup cell does `from src.notebook.render import *`). Re-select the `.venv` (3.14) kernel.

## Per-feature understanding & quality (OK/NOK)

Each Bronze/Silver layer produces the **same per-feature model** (`src/common/profiling.py`):
type-aware synthesis + an **OK/NOK status** badge + plots. Status criteria are declared in
`src/common/quality.py`:
- `FEATURE_CHECKS` — by feature name (all sources/layers);
- `SOURCE_FEATURE_CHECKS` — scoped to `(source, feature)` (e.g. `machine_id` is a primary key
  only in the `machine` dimension).
Reusable checks: `NO_MISSING`, `NO_DUPLICATES`, `VALID_DATE_FORMAT`, `VALID_TIME_FORMAT`,
`UNIQUE_PER_MACHINE` / `NO_MISSING_HOURS`, `IN_CRITICALITY_DOMAIN`, `STRICTLY_POSITIVE`,
`NOT_IN_FUTURE`, `SAME_DISTINCT_AS_OPERATOR_NAME`. Display tweaks: `ORDINAL_FEATURES`,
`HOURLY_PER_MACHINE_FEATURES`, `NO_OUTLIER_FEATURES`.

Per-layer artefacts under `artifacts/ingestions/<source>/<run>/{bronze,silver}/`:
`<source>.csv` (DVC), `1.<i>_box_*`, `2.<i>_dist_*`, `3.<i>_count_*`, `4.<i>_kw_*`,
`5.<i>_heat_*`, `6.<i>_ts_*`, `run_report.md`, `dataset_report.md`, `text_encodings.json`.
Numeric features per source: incidents Bronze/Silver = ∅ (severity = count chart only);
telemetry = the 5 params; maintenance = `duration_hours`; machine dim = capacities. Gold has
its own `FEATURES_NUMERIC` / `FEATURES_COUNT` in `src/gold/features.py`.

## Source data

**`data/raw/incidents.csv`** — `incident_id`, `date` (YYYY-MM-DD), `time` (HH:MM:SS),
`operator_name` (**PII**), `machine_id`, `severity` (1–5), `operator_badge` (**PII**),
`comment` (**potential PII**), `shift` (matin/apres-midi/nuit), and the 9 `type_*` **signals**
(binary 0/1; `SIGNAL_COLUMNS` in `config.py`). PII handling: `operator_name`/`operator_badge`
→ truncated HMAC-SHA256 **from Bronze** (never persisted in clear); `comment` kept raw in
Bronze, flagged `comment_pii_flag` downstream.

**`data/raw/telemetry.csv`** — hourly per machine, no PII: `machine_id`, `timestamp`,
`temperature_c`, `pressure_bar`, `voltage_mean_v`, `rotation_mean_rpm`, `pieces_produced`.
Silver: dedup (mean) + per-machine **time interpolation** (ffill/bfill at edges) + z-score on
the 4 measures; **no outlier winsorisation** (it piled an artificial spike at the fence);
`pieces_produced` kept raw.

**`data/raw/machines.sql`** — PostgreSQL dump loaded into local **SQLite** via SQLAlchemy ORM
(`src/sources/machines/models.py`), read with `pandas.read_sql`; `machine_code` renamed
`machine_id`. Two medallion sources: `machines` (maintenance facts) and `machine`
(referential dimension, **Bronze-only**, coherence checks: PK no-duplicate, criticality
domain, positive capacities, commissioning date not in the future).

## Cross-source analyses

`src/analyses/` combines sources (joins on `machine_id` / `incident_id`), reusing source
loaders; artefacts under `artifacts/analyses/cross_source/<run>/` (`machine_profile.csv` +
plots + reports). Run: `uv run python scripts/run_cross_source.py`.

## Add a new source (checklist)

Permanent instruction: do the whole checklist at once, reusing `src/common/` and mirroring the
existing sources (the runner stays **thin**).

1. **Schema & paths** in `src/config.py`.
2. **`src/sources/<name>/`**: `loader.py` (`load_<name>()`, raw typed, no treatment); thin
   `runner.py` exposing `SOURCE_NAME`, `TABLE`, `BRONZE_NUMERIC`/`SILVER_NUMERIC`,
   `load_bronze()` (+ `pseudonymise_operators` if operator PII), `to_silver(bronze_df) ->
   (df, report)` via `apply_processing(...)`. Gold has **no per-source `to_gold`**: the single
   `gold.features` is built in `src/gold/features.py` — extend the builder if the new source
   should contribute. Optional hooks (read via `getattr`): `COUNT_FEATURES`/`COUNT_LABEL`,
   `KEYWORD_BARS`, `HEATMAPS`, `TIMESERIES`, `OVERVIEW`, `FEATURE_PLOTS`, `MACHINE_COL`,
   `CUMULATIVE`, `BARS_BY_MACHINE`, `PROCESSING` (`ProcessingConfig`), `BRONZE_ONLY`.
3. **No treatment in Bronze** (except operator pseudonymisation). Treatment in Silver
   (`to_silver`); derived features in the unified Gold builder.
4. **Register** in `src/sources/registry.py` (`SOURCE_SPECS` via `_spec(<name>_runner)`) →
   the orchestrator handles Bronze + Silver + DB load automatically.
5. **Quality** (optional): declare checks in `src/common/quality.py`.
6. **`scripts/run_<name>.py`**: minimal CLI (`run_source_by_name("<name>")`, Agg backend,
   `--no-db`).
7. **Notebook**: add the source under chapters 1/2 (`show_per_feature_spec` /
   `show_silver_*` from `src.notebook.render`); Gold (ch. 3) is the single table.
8. **Document** in `CLAUDE.md` / `README.md` / this file.

> Known refactor lead (see the optimisation analysis): the source↔table↔key mapping is still
> duplicated across `registry`, `ingestion/schemas`, `database/models_bronze`, `gold/features`,
> `silver/refine`, `orchestrator`. Consolidating it into `SourceSpec` is the main reusability win.
