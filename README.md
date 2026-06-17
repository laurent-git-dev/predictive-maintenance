# Industrial Predictive Maintenance — Data Pipeline

Orchestrated, **multi-source** data pipeline following a **medallion architecture**.
For each source in `data/raw/` (2 CSV + 1 SQL) it builds two layers:

- **Bronze** — raw, typed data (operator PII pseudonymised on the way in);
- **Silver** — processed data (feature engineering, encoding, imputation, outliers).

Each layer produces the **same per-feature understanding** (reports + graphs) and is
loaded into its own PostgreSQL schema (`bronze.*`, `silver.*`). A cross-source analysis
runs at the end. Re-run everything with one command whenever the input data changes.
(**Gold** is planned next, with the same mechanics.)

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

## 3a. Medallion layers & per-feature output

Each per-source CLI builds **both layers** and writes them under
`artifacts/ingestions/<source>/AAAAMMJJHHMM/{bronze,silver}/`:

```bash
uv run python scripts/run_incidents.py     # Bronze + Silver for incidents
```

All sources/layers share the same **per-feature** output model: for each numeric
feature, a boxplot across machines (`1.<i>_box_<feature>.png`) and a distribution
(`2.<i>_dist_<feature>.png`); plus `run_report.md` (technical) and `dataset_report.md`
(shareable per-feature profile, synthesis adapted to each column's type). Each run
updates the source's `runs_registry.json`.

| File (per layer) | Description |
|---|---|
| `<source>.csv` | Layer dataset (gitignored; versionable via DVC) |
| `1.<i>_box_<feature>.png` | Boxplot of a numeric feature across machines |
| `2.<i>_dist_<feature>.png` | Distribution (histogram + density/KDE) of a feature |
| `run_report.md` | Technical layer report (metrics + missing per column) |
| `dataset_report.md` | Shareable per-feature synthesis report |

Numeric features per layer: **incidents** — Bronze `severity`; Silver `severity`,
`n_active_signals`, `confidence_index`. **telemetry** — the 5 parameters (Bronze = Silver).
**machines** — `duration_hours` (Bronze = Silver).

DB tables: `{bronze,silver}.incidents`, `{bronze,silver}.telemetry`,
`{bronze,silver}.maintenance`.

> **Signals** are the columns prefixed by `type_` (binary 0/1 anomaly flags).

---

## 3b. Telemetry source

A second data source: hourly machine **telemetry** (no PII). Drop the CSV into
`data/raw/telemetry.csv`, then:

```bash
uv run python scripts/run_telemetry.py
```

Columns: `machine_id, timestamp, temperature_c, pressure_bar, voltage_mean_v,
rotation_mean_rpm, pieces_produced`. Bronze = raw load; Silver = median imputation +
IQR outlier treatment on the 5 parameters.

---

## 3c. Machines / maintenance source (SQL)

A third source: a **PostgreSQL dump** (`data/raw/machines.sql`) with a `machine`
referential and a `maintenance` events table. It is loaded into a local **SQLite**
database via **SQLAlchemy ORM** (no PostgreSQL server needed), then read into
pandas.

```bash
uv run python scripts/run_machines.py
```

Bronze = raw maintenance events; Silver = encoding (`maintenance_type`, `component`)
+ IQR outlier treatment on `duration_hours`.

---

## 3d. Cross-source analysis

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
