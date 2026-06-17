# Industrial Predictive Maintenance — Data Pipeline

Orchestrated, **multi-source** data pipeline. For each source in `data/raw/`
(2 CSV + 1 SQL) it chains **ingestion → understanding (reports/graphs) →
processing (anonymisation, encoding, imputation, outliers) → loading into a
PostgreSQL database**, then runs a cross-source analysis. Re-run it with one
command whenever the input data changes.

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
uv run python scripts/run_pipeline.py     # all sources: ingest → understand → process → load DB
#                                           then the cross-source analysis
uv run python scripts/run_pipeline.py --no-db   # skip the database stage
```

- Idempotent and **re-runnable**: tables are fully reloaded (`to_sql` replace).
- If PostgreSQL is not running, the **DB stage is skipped with a warning** (the rest runs).
- Interactive exploration of every phase: `notebooks/pipeline.ipynb`.

Per-source CLIs are still available (`scripts/run_{incidents,telemetry,machines}.py`,
`run_cross_source.py`, `run_all.py`).

---

## 3a. Per-source usage (understanding only)

Drop the source CSV into `data/raw/incidents.csv`, then:

```bash
uv run python scripts/run_incidents.py --input data/raw/incidents.csv
```

> Run **all sources** at once with `uv run python scripts/run_all.py`.

The script creates `artifacts/ingestions/incidents/AAAAMMJJHHMM/` with:

| File | Description |
|---|---|
| `incidents_anonymized.csv` | Cleaned, anonymised, enriched dataset (confidence index) |
| `1.1_dist_incidents_day.png` | Incident distribution per day |
| `1.2_dist_incidents_week.png` | Incident distribution per week |
| `1.3_dist_incidents_shift.png` | Incident distribution per shift |
| `2.1_hist_incidents_machine.png` | Incidents per machine |
| `2.2_hist_incidents_operator.png` | Incidents per operator (pseudonymised) |
| `2.3_hist_incidents_signal.png` | Incidents per signal |
| `2.4_hist_incidents_confidence.png` | Incidents per confidence index |
| `3.1_corr_severity_signals.png` | Correlation: severity / signals |
| `3.2_corr_severity_comment.png` | Correlation: severity / comment category (chi-square + Cramer's V) |
| `run_report.md` | Technical run report (metrics, anonymisation, confidence) |
| `dataset_report.md` | Shareable synthesis report (business) compiling all graphs |

Graphs are named with an ordered numeric prefix. And the run updates
`artifacts/ingestions/incidents/runs_registry.json`.

> **Signals** are the columns prefixed by `type_` (binary 0/1 anomaly flags).

---

## 3b. Telemetry source

A second data source: hourly machine **telemetry** (no PII, no anonymisation).
Drop the CSV into `data/raw/telemetry.csv`, then:

```bash
uv run python scripts/run_telemetry.py --input data/raw/telemetry.csv
```

Columns: `machine_id, timestamp, temperature_c, pressure_bar, voltage_mean_v,
rotation_mean_rpm, pieces_produced`.

Produces `artifacts/ingestions/telemetry/AAAAMMJJHHMM/` with one boxplot per
parameter (distribution per machine, `1.1_box_*.png` … `1.5_box_*.png`), a
`run_report.md`, and updates the telemetry `runs_registry.json`.

---

## 3c. Machines / maintenance source (SQL)

A third source: a **PostgreSQL dump** (`data/raw/machines.sql`) with a `machine`
referential and a `maintenance` events table. It is loaded into a local **SQLite**
database via **SQLAlchemy ORM** (no PostgreSQL server needed), then read into
pandas.

```bash
uv run python scripts/run_machines.py --input data/raw/machines.sql
```

Produces `artifacts/ingestions/machines/AAAAMMJJHHMM/` with four plots
(maintenance per machine, duration per machine, proactive vs reactive, per
component), a `run_report.md`, and updates the machines `runs_registry.json`.

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
# Version an anonymised dataset produced by a run
dvc add artifacts/ingestions/incidents/AAAAMMJJHHMM/incidents_anonymized.csv
git add artifacts/ingestions/incidents/AAAAMMJJHHMM/incidents_anonymized.csv.dvc
git commit -m "feat(data): anonymised dataset run AAAAMMJJHHMM"

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
