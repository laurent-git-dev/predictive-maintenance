# Industrial Predictive Maintenance — Data Pipeline

Orchestrated, **multi-source** data pipeline following a **medallion architecture**.
For each source in `data/raw/` (2 CSV + 1 SQL) it builds Bronze and Silver, then a single
unified Gold table:

- **Bronze** — raw, typed data (operator PII pseudonymised on the way in);
- **Silver** — **treated** data, built **from the `bronze.*` DB tables**: a reject policy
  (rows flagged `duplicate`/`missing` are kept & corrected by the treatments, others are
  rejected) then dedup, dimension merge, encoding, imputation, time interpolation,
  normalization — no feature engineering;
- **Gold** — **one cross-source table** `gold.features`, grain **(machine_id, 1-hour
  window)**: telemetry is the spine, with engineered **memory** (rolling mean/max/std),
  **trend** (OLS slope), **anomaly** (z-scores) and **context** features (incident / signal /
  maintenance history), plus **failure labels** at +6/12/24/48h. Decision instant = window end.

Bronze/Silver produce the **same per-feature understanding** (reports + graphs + an
**OK/NOK quality status**) loaded per source into `bronze.*` / `silver.*`; Gold loads the
single `gold.features` table. A cross-source analysis runs at the end. Re-run everything
with one command whenever the input data changes.

**Batch traceability** — each `run_pipeline` execution opens a `batch_id` and records **one
row per processing step** in `meta.processing_runs` (input/output refs, start/end, status,
rows read/ingested/rejected, quality flag, git sha, output hash). Filtering on `batch_id`
gives the full lineage **DataLake → bronze → silver → gold** (`src/lineage/`, soft quality
checks). Schema via Alembic: `uv run alembic upgrade head`.

**Four Bronze sources** are declared in the registry: `incidents`, `telemetry`, `machine`
(the referential **dimension**) and `machines` (the **maintenance** facts). **Silver has 3
sources** — `incidents`, `telemetry`, `maintenance` (the `machine` dimension is
**Bronze-only**, merged first into the maintenance facts; no `silver.machine`). **Gold is a
single table** built from the three Silver frames (`src/gold/features.py`). The exploration
notebook is organised in **3 chapters** (`1. BRONZE` → `2. SILVER` → `3. GOLD`); **each
source** follows the same template — **PREVIEW** (per-feature understanding) → **PROCESSING**
(per-feature transformation) → **OVERVIEW** (permanent + inline analysis) — with layer-level /
cross-source material in a per-chapter appendix.

---

## 1. Prerequisites

- **Python 3.12** (see `.python-version`)
- **[uv](https://docs.astral.sh/uv/)** for environment management
- **Docker** (PostgreSQL via `docker-compose.yml`) for the database stage
- **Git** and **DVC** for code / data versioning
- **SQLAlchemy + Alembic** (Bronze schema/migrations) and **Pydantic** (Bronze validation)

> Create/upgrade the Bronze schema once PostgreSQL is up: `uv run alembic upgrade head`
> (the pipeline also runs an idempotent `create_all` safety net).

> ⚠️ **Corporate network**: if uv fails with `invalid peer certificate:
> UnknownIssuer`, add `--native-tls` to the uv commands (or set
> `UV_SYSTEM_CERTS=true`).

---

## 2. Installation

```bash
# 1. Sync the environment (.venv created automatically)
uv sync                       # or: uv sync --native-tls

# 2. Configure secrets / DB settings
cp .env.example .env
# edit .env: set ANONYMIZATION_SALT (and POSTGRES_* if you change defaults)
#   python -c "import secrets; print(secrets.token_hex(32))"
```

---

## 3. Quickstart — full pipeline (recommended)

```bash
docker compose up -d                      # start PostgreSQL
uv run python scripts/run_pipeline.py     # all sources: Bronze + Silver + Gold (understand → load DB)
#                                           then the cross-source analysis
uv run python scripts/run_pipeline.py --no-db   # skip the database stage
```

- Idempotent and **re-runnable**: tables are fully reloaded per schema (`to_sql` replace).
- If PostgreSQL is not running, the **DB stage is skipped with a warning** (the rest runs).
- Interactive exploration of every layer: `notebooks/pipeline.ipynb`.

Per-source CLIs are still available (`scripts/run_{incidents,telemetry,machines}.py`,
`run_cross_source.py`), each accepting `--no-db`.

---

## 3.1 Medallion layers & per-feature output

Each per-source CLI builds **Bronze + Silver** and writes them under
`artifacts/ingestions/<source>/AAAAMMJJHHMM/{bronze,silver}/`. The unified **Gold** table is
built only by the full pipeline (`run_pipeline.py`) — it needs all three Silver frames — and
written under `artifacts/gold/<run>/`:

```bash
uv run python scripts/run_incidents.py     # Bronze + Silver for incidents
```

All sources/layers share the same **per-feature** output model: every column gets a
type-aware synthesis and an **OK/NOK status** (green/red badge), plus type-specific
graphs. `run_report.md` is the technical report; `dataset_report.md` is the shareable
per-feature profile. Each run updates the source's `runs_registry.json`.

| File (per layer) | Description |
|---|---|
| `<source>.csv` | Layer dataset (gitignored; versionable via DVC) |
| `1.<i>_box_<feature>.png` | Boxplot of a numeric feature across machines (if a machine column is present) |
| `2.<i>_dist_<feature>.png` | Distribution (histogram + density/KDE) of a numeric feature |
| `3.<i>_count_<feature>.png` | Count per category (`COUNT_FEATURES` hook) |
| `4.<i>_kw_<feature>.png` | Keyword breakdown in free text (`KEYWORD_BARS` hook) |
| `5.<i>_heat_<row>_<col>.png` | Row-normalised crosstab heatmap (`HEATMAPS` hook) |
| `6.<i>_ts_<feature>.png` | Per-machine time series (`TIMESERIES` hook) |
| `run_report.md` | Technical layer report (metrics + missing per column) |
| `dataset_report.md` | Shareable per-feature synthesis (synthesis + status + graphs) |

The type-aware synthesis covers: numeric (range, quartiles, mean/std/skew, an **outlier
table** by IQR and z-score), boolean (0/1 shares), ordinal (light), datetime (range; a
per-machine QC table for hourly series). **Quality status** criteria are declared in
`src/common/quality.py` (`FEATURE_CHECKS` by feature name, `SOURCE_FEATURE_CHECKS` scoped
to a source — e.g. `machine_id` is a primary key only in the `machine` dimension).

DB tables — **Bronze (4)**: `bronze.{incidents, telemetry, machine, maintenance}` —
**Alembic-managed** schema, ingested via SQLAlchemy with **Pydantic validation** that adds
`parse_ok` / `parse_reason` (type / domain / missing / duplicate flags; **no value modified**,
invalid rows kept & flagged); **Silver (3)**: `silver.{incidents, telemetry, maintenance}`
(no `silver.machine` — the dimension is merged into `silver.maintenance`); **Gold (1)**:
`gold.features` — a single cross-source table at (machine_id, hour) grain (see *Gold layer* below).

> **Signals** are the columns prefixed by `type_` (binary 0/1 anomaly flags).

---

## 3.2 Telemetry source

A second data source: hourly machine **telemetry** (no PII). Drop the CSV into
`data/raw/telemetry.csv`, then:

```bash
uv run python scripts/run_telemetry.py
```

Columns: `machine_id, timestamp, temperature_c, pressure_bar, voltage_mean_v,
rotation_mean_rpm, pieces_produced`. Bronze = raw load; Silver (treatment) = dedup (mean) +
per-machine time interpolation (linear in time, ffill/bfill at edges) + z-score on the 4
physical measures. Outliers are **not** winsorised (IQR clipping piled an artificial spike
at the fence); raw extremes are kept and `pieces_produced` stays raw. In Gold, telemetry is
the **spine** of the unified `gold.features` table (capacity/utilization features derived there). Extra hooks: a per-machine `TIMESERIES`
(daily/weekly piece production) and a source `OVERVIEW` (measures over time); `timestamp`
is checked for per-machine duplicates and missing hourly slots.

---

## 3.3 Machines source (SQL): `machine` dimension + `maintenance` facts

The third input is a **PostgreSQL dump** (`data/raw/machines.sql`) with two tables,
loaded into a local **SQLite** database via **SQLAlchemy ORM** (no PostgreSQL server
needed) and read into pandas. It has **two Bronze sources** but a **single Silver table**
(`silver.maintenance`):

```bash
uv run python scripts/run_machines.py   # the maintenance (facts) source
```

- **`maintenance`** facts (source `machines`; notebook **Machines/maintenance**):
  Bronze = raw events; Silver **merges the machine dimension first** (all attributes incl.
  `commissioning_date`, on `machine_id` — star schema) and encodes `maintenance_type`,
  `action_type`, `component`, `criticality`, `production_line`, `location`, `model`
  (`duration_hours` kept raw). In Gold, maintenance events feed **context features** in
  `gold.features` (corrective/proactive counts over {5,10,20,30,60d} + days since last).
- **`machine`** dimension / referential (source `machine`; notebook **Machines/machine**;
  one row per machine): **Bronze-only** (`BRONZE_ONLY = True`, **no `silver.machine`**). The
  **Bronze layer verifies coherence** (status: `machine_id` primary key — no missing, **no
  duplicate** —, `criticality` ∈ {LOW, MEDIUM, HIGH}, positive capacities, commissioning date
  not in the future). Being a dimension, it has no per-machine boxplot; it shows capacity
  distributions and category counts. Its attributes are encoded when merged into
  `silver.maintenance`. It is run by the full pipeline (`run_pipeline.py`).

---

## 3.4 Gold layer (unified feature table)

The full pipeline finishes by consolidating the **`silver.*` DB tables** into **one
training-ready table** `gold.features` (`src/gold/features.py` — `build_gold_from_db` reads
`silver.*`), grain **(machine_id, 1-hour window)**, ~216 columns. **Use case**: predict a
**failure = incident of severity ≥ 4** at horizons **+6/12/24/48h**. Decision instant
**t = `window_end`**: features look back up to & including the current hour, labels look
strictly after (NaN if censored at the series end; the row is kept). Gold stats:
`src/gold/stats.py` (rows, feature counts by group, label positive rates per horizon, censored).

- **Identifiers** — `machine_id`, `window_start`, `window_end`, `split_set` (`"train"`).
- **Memory** — 5 telemetry measures × {2,3,4,6,12,24,48}h × {mean, max, std}.
- **Trend** — 5 measures × {2,3,4,5,6}h OLS slope per hour.
- **Anomaly** — per measure: z-score vs trailing 24h and vs the machine over all data.
- **Context** — incidents (count + max severity over {6,12,24,48h,7d} + recency), signal
  activations (9 signals × same horizons), maintenance (corrective/proactive counts over
  {5,10,20,30,60d} + recency).
- **Labels** — `label_failure_next_{6,12,24,48}h` (1 if a failure in `(t, t+H]`; NaN if
  the future window is censored at the series end).

No leakage by construction (features use past/present only; `z_machine` uses full-history
stats — recompute on the train split later). In the notebook, chapter **3. GOLD** covers it:
**3.1.1 PREVIEW** (build + per-feature review), **3.1.2 PROCESSING** (per-group build doc),
**3.1.3 OVERVIEW** (permanent + inline analysis).

---

## 3.5 Cross-source analysis

Cross-source analyses combine the sources (joined on `machine_id` /
`incident_id`). They live in `src/analyses/` and reuse the source loaders.

```bash
uv run python scripts/run_cross_source.py
```

Produces `artifacts/analyses/cross_source/AAAAMMJJHHMM/` with the joined
`machine_profile.csv`, three cross plots (incidents vs maintenance, reactive vs
severity, telemetry vs incidents), a `run_report.md`, and a dedicated registry.
Interactive exploration: `notebooks/pipeline.ipynb`.

---

## 4. Anonymisation — technical rationale

The GDPR distinguishes **anonymisation** (irreversible) from **pseudonymisation**
(reversible with separately stored information). The pipeline applies **strong
pseudonymisation**:

| Column | Treatment | Rationale |
|---|---|---|
| `operator_name` | Truncated **HMAC-SHA256** + **secret salt** (pepper) | A plain `SHA-256(name)` is reversible through a dictionary attack (small name space). HMAC with a secret key prevents re-identification, while staying **deterministic** (longitudinal analysis stays possible). |
| `operator_badge` | Opaque identifier `OP_xxxxxx` (HMAC) | No mapping table stored in the repository. |
| `comment` | Kept + `comment_pii_flag` column | Free text potentially nominative: manual review recommended. |

The **salt** (`ANONYMIZATION_SALT`) is stored in `.env` (ignored by Git). It must
stay **constant** across runs (pseudonym consistency) and **secret**
(non-reversibility). For *irreversible* anonymisation, drop the key or rely on
**differential privacy** on published aggregates.

---

## 5. Reporting confidence index

`confidence_index = number of active signals / total number of signals`

Business assumption: an incident corroborated by several simultaneous signals is
more reliable than one relying on a single isolated signal.

---

## 6. Data versioning (DVC)

Raw data and produced datasets are **never** committed to Git: only the `.dvc`
pointers are.

```bash
# Version the bronze/silver datasets produced by a run
dvc add artifacts/ingestions/incidents/AAAAMMJJHHMM/bronze/incidents.csv \
        artifacts/ingestions/incidents/AAAAMMJJHHMM/silver/incidents.csv
git add artifacts/ingestions/incidents/AAAAMMJJHHMM/bronze/incidents.csv.dvc \
        artifacts/ingestions/incidents/AAAAMMJJHHMM/silver/incidents.csv.dvc
git commit -m "feat(data): bronze/silver datasets run AAAAMMJJHHMM"

# Push the data to the local DVC remote
dvc push
```

---

## 7. Code quality

```bash
uv run ruff check src scripts      # lint
uv run black src scripts           # formatting
```

---

## 8. Project structure

See [CLAUDE.md](CLAUDE.md) for the detailed tree, data schema and conventions.
