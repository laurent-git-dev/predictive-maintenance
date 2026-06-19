# Industrial Predictive Maintenance — Data Pipeline

Orchestrated, **multi-source** data pipeline following a **medallion architecture**.
For each source in `data/raw/` (2 CSV + 1 SQL) it builds two layers:

- **Bronze** — raw, typed data (operator PII pseudonymised on the way in);
- **Silver** — processed data (feature engineering, encoding, imputation, outliers).

Each layer produces the **same per-feature understanding** (reports + graphs + an
**OK/NOK quality status** per feature) and is loaded into its own PostgreSQL schema
(`bronze.*`, `silver.*`). A cross-source analysis runs at the end. Re-run everything with
one command whenever the input data changes. (**Gold** is planned next, with the same
mechanics.)

**Four sources** are declared in the registry: `incidents`, `telemetry`, `machine` (the
referential **dimension**) and `machines` (the **maintenance** facts); in Silver the
maintenance facts are **enriched** with the machine dimension attributes (star schema).
The exploration notebook is organised **by layer** (Bronze → Processing → Silver), each
with a per-feature view, a per-source overview and inline analysis.

---

## 1. Prerequisites

- **Python 3.12** (see `.python-version`)
- **[uv](https://docs.astral.sh/uv/)** for environment management
- **Docker** (PostgreSQL via `docker-compose.yml`) for the database stage
- **Git** and **DVC** for code / data versioning

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
uv run python scripts/run_pipeline.py     # all sources: Bronze + Silver (understand → load DB)
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

Each per-source CLI builds **both layers** and writes them under
`artifacts/ingestions/<source>/AAAAMMJJHHMM/{bronze,silver}/`:

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

DB tables: `{bronze,silver}.incidents`, `{bronze,silver}.telemetry`,
`{bronze,silver}.machine` (dimension) and `{bronze,silver}.maintenance` (facts, Silver
enriched with the machine attributes).

> **Signals** are the columns prefixed by `type_` (binary 0/1 anomaly flags).

---

## 3.2 Telemetry source

A second data source: hourly machine **telemetry** (no PII). Drop the CSV into
`data/raw/telemetry.csv`, then:

```bash
uv run python scripts/run_telemetry.py
```

Columns: `machine_id, timestamp, temperature_c, pressure_bar, voltage_mean_v,
rotation_mean_rpm, pieces_produced`. Bronze = raw load; Silver = median imputation +
IQR outlier treatment on the 5 parameters. Extra hooks: a per-machine `TIMESERIES`
(daily/weekly piece production) and a source `OVERVIEW` (measures over time); `timestamp`
is checked for per-machine duplicates and missing hourly slots.

---

## 3.3 Machines source (SQL): `machine` dimension + `maintenance` facts

The third input is a **PostgreSQL dump** (`data/raw/machines.sql`) with two tables,
loaded into a local **SQLite** database via **SQLAlchemy ORM** (no PostgreSQL server
needed) and read into pandas. It yields **two medallion sources**:

```bash
uv run python scripts/run_machines.py   # the maintenance (facts) source
```

- **`maintenance`** facts (source `machines`; notebook **Machines/maintenance**):
  Bronze = raw events; Silver = encoding (`maintenance_type`, `component`) + IQR outlier
  treatment on `duration_hours`, then **enriched** by joining the machine dimension
  attributes on `machine_id` (`criticality`, `production_line`, `location`, `model`,
  capacities).
- **`machine`** dimension / referential (source `machine`; notebook **Machines/machine**;
  one row per machine): the **Bronze layer verifies coherence** (status: `machine_id`
  primary key — no missing, **no duplicate** —, `criticality` ∈ {LOW, MEDIUM, HIGH},
  positive capacities, commissioning date not in the future). Silver encodes `criticality`.
  Being a dimension, it has no per-machine boxplot; it shows capacity distributions and
  category counts. It is run by the full pipeline (`run_pipeline.py`).

---

## 3.4 Cross-source analysis

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
