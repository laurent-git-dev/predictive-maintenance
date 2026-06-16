# Industrial Predictive Maintenance — Step 2: Data Ingestion & Governance

Ingestion pipeline for industrial incident reports: **loading → anonymisation →
exploratory data analysis (EDA) → versioned dataset**.

Each run produces a timestamped folder containing the anonymised dataset, the
analysis plots and a report, and updates a runs registry.

---

## 1. Prerequisites

- **Python 3.12** (see `.python-version`)
- **[uv](https://docs.astral.sh/uv/)** for environment management
- **Git** and **DVC** for code / data versioning

> ⚠️ **Corporate network**: if uv fails with `invalid peer certificate:
> UnknownIssuer`, add `--native-tls` to the uv commands (or set
> `UV_SYSTEM_CERTS=true`).

---

## 2. Installation

```bash
# 1. Sync the environment (.venv created automatically)
uv sync                       # or: uv sync --native-tls

# 2. Configure the anonymisation salt (secret, outside the repository)
cp .env.example .env
# then edit .env and set ANONYMIZATION_SALT
#   python -c "import secrets; print(secrets.token_hex(32))"
```

---

## 3. Usage

Drop the source CSV into `data/raw/incidents.csv`, then:

```bash
uv run python scripts/run_ingestion.py --input data/raw/incidents.csv
```

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
| `3.2_corr_severity_comment.png` | Correlation: severity / comment presence |
| `run_report.md` | Technical run report (metrics, anonymisation, confidence) |
| `dataset_report.md` | Shareable synthesis report (business) compiling all graphs |

Graphs are named with an ordered numeric prefix. And the run updates
`artifacts/ingestions/incidents/runs_registry.json`.

> **Signals** are the columns prefixed by `type_` (binary 0/1 anomaly flags).

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
