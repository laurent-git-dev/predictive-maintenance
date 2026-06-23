# Technical documentation — Predictive-maintenance pipeline

Exhaustive technical reference for the application: development environment, software
architecture, repository layout, and how to run every treatment / tool / database operation.

> **Companion documents.** Conventions & gotchas: [`CLAUDE.md`](../CLAUDE.md). Architecture map:
> [`ARCHITECTURE.md`](ARCHITECTURE.md). Decisions & rationale: [`adr/`](adr/README.md). Operations
> (run → DVC → push): [`RUNBOOK.md`](../RUNBOOK.md). Modeling & evaluation: [`MODELING.md`](MODELING.md).
> Business view of the Gold dataset: [`GOLD_DATASET_FR.md`](GOLD_DATASET_FR.md).
> Language note: code, docs and reports are in **English** (project convention); the business
> document is in French for the client. The source code in `src/` is the ultimate source of truth.

---

## 1. Purpose

The application turns four raw industrial data sources into a single **training-ready feature
table** (`gold.features`) to **predict machine failures ahead of time**. It is built as a
**medallion pipeline** (Bronze → Silver → Gold) chained through PostgreSQL, with full lineage,
data-quality flags, automated tests, and an experiment harness to produce comparable dataset
versions.

---

## 2. Development environment

### 2.1 Platform & shell
- **OS**: Windows 11, VS Code. Interactive shell is **PowerShell** (provide PowerShell commands
  when copy-pasting on the host).
- **Corporate proxy (Avast TLS interception)** breaks default certificate validation:
  - `uv` / `dvc` network ops → add `--native-tls` (or `UV_SYSTEM_CERTS=true`).
  - `curl` → `--ssl-no-revoke`.
  - `git` (already set in the repo's local config) → `http.sslBackend=schannel` +
    `http.schannelCheckRevoke=false`.

### 2.2 Language & package manager
- **Python 3.14** (`.python-version`; `requires-python >=3.12`).
- **[uv](https://docs.astral.sh/uv/)** manages the virtualenv (`.venv`) and the lockfile (`uv.lock`).
  The project is an **application, not a library** (`[tool.uv] package = false`): modules under
  `src/` are imported via `sys.path` (a root `conftest.py` injects the project root for tests).

```powershell
uv sync                     # create/refresh .venv from uv.lock (+ dev group)
uv add <pkg>                # add a runtime dependency        (+ --native-tls behind the proxy)
uv add --dev <pkg>          # add a dev dependency
uv run <cmd>                # run a command inside the venv
```

### 2.3 Dependencies (`pyproject.toml`)
- **Runtime**: `pandas`, `scipy`, `matplotlib`, `sqlalchemy` (2.0), `alembic`, `pydantic` (2),
  `psycopg2-binary`, `dvc`. `pydantic-settings` is used for typed settings.
- **Dev**: `ruff`, `black`, `mypy`, `pytest`, `ipykernel`.

### 2.4 Database (PostgreSQL via Docker)
- Started with `docker compose up -d` (port **5432**; credentials from `.env`).
- Connection settings live in **`src/settings.py`** (`pydantic-settings`, read from the
  environment / `.env`; defaults match `docker-compose.yml`:
  `predictive` / `predictive` / `predictive_maintenance` @ `localhost:5432`).
- Schemas/tables are managed by **Alembic** (`uv run alembic upgrade head`). If PostgreSQL is
  down, the pipeline still runs with `--no-db` (file-only fallback).

### 2.5 Secrets & data security
- **`.env`** holds at least `ANONYMIZATION_SALT` (operator PII pseudonymisation). The pipeline
  **fails fast** at startup if the salt is missing/placeholder (`src/settings.require_salt`).
- `data/raw/` is **never** committed (gitignored + DVC); operator PII is pseudonymised from
  Bronze (HMAC-SHA256). A Claude-Code guard hook also blocks edits to `data/raw/` and `.env`.

### 2.6 Data versioning (DVC)
- Produced CSVs are versioned with DVC against a **local remote** (no network):
  `uv run dvc add <…>.csv` → commit the `.dvc` sidecar → `uv run dvc push`. See `RUNBOOK.md §2`.

### 2.7 Quality tooling
| Tool | Command | Scope |
|---|---|---|
| Lint | `uv run ruff check src scripts tests conftest.py alembic` | E/F/I/UP/B rules, line 100 |
| Format | `uv run black src scripts tests conftest.py alembic` | line 100 |
| Types | `uv run mypy` | `src/` (config in `pyproject.toml`, `ignore_missing_imports`) |
| Tests | `uv run pytest -q` | 13 test files; **unit** + **golden** (characterisation) |

- **Golden tests** freeze Bronze/Silver row counts and Silver/Gold content **hashes**, so any
  refactor that changes a result is caught immediately. They need `data/raw/` and are **skipped**
  when absent (e.g. in CI).
- **CI** (`.github/workflows/ci.yml`): on push/PR to `master`, GitHub Actions runs
  `ruff` + `black --check` + `mypy` + `pytest -m "not golden"` via uv.

### 2.8 Claude Code integration (`.claude/`, optional dev productivity)
- `settings.json` — shared permissions allow-list (read-only/quality commands) + **hooks**:
  auto-format edited Python (`ruff --fix` + `black`), a path guard (block `data/raw`/`.env`
  writes), and a Stop quality gate (ruff + unit tests on changed `*.py`).
- `skills/` — `/add-source`, `/run-pipeline`, `/commit-run`, `/quality-gate`. See `.claude/README.md`.

---

## 3. Software architecture

### 3.1 Medallion, chained through the database
Raw files → **`bronze.*`** → **`silver.*`** → **`gold.features`**; each layer reads the previous
one **from PostgreSQL** (ADR 0001). A single **cross-source analysis** runs at the end.

```
data/raw/  ──load──▶  bronze.*  ──refine──▶  silver.*  ──build──▶  gold.features
 (CSV/SQL)            (4 tables)             (3 tables)            (1 table, 253 cols)
                         │                       │                      │
                    validate/flag          reject policy +         features + labels
                    (parse_ok/reason)       treatments              (causal ≤ t)
                         └───────────────── meta.processing_runs (lineage) ─────────┘
```

### 3.2 Three tiers + dependency rule (ADR 0006)
Enforced rule: **kernel ← framework ← use-case** (the framework never imports `src.usecase.*`).

- **Kernel** (`src/config.py`, `src/quality.py`, `src/settings.py`): passive configuration —
  column names / schemas / thresholds, per-feature quality criteria, and runtime settings.
- **`src/framework/`**: generic, reusable medallion engine (no maintenance specifics).
- **`src/usecase/`**: this predictive-maintenance application (sources, schemas, Gold spec, …).

### 3.3 Layers

- **Bronze** (`usecase/ingestion/`, `usecase/db/models_bronze.py`) — raw typed load + operator
  pseudonymisation; a **non-destructive Pydantic validation** adds `parse_ok` / `parse_reason`
  (type / domain / range / missing / format / duplicate) **without changing any value**; all rows
  are loaded (SQLAlchemy ORM, schema managed by Alembic). 4 sources: `incidents`, `telemetry`,
  `machine` (dimension, Bronze-only), `machines` (maintenance facts). ADR 0002.
- **Silver** (`usecase/silver/refine.py`) — reads `bronze.*`; **reject policy** (rows whose only
  anomalies are `duplicate`/`missing` are kept & corrected; `type`/`domain`/`format`/`range`/
  `invalid` are rejected); then treatments (`apply_processing`: dedup → interpolate → encode →
  impute → outliers → normalize) → `silver.*`. The `machine` dimension is denormalised into
  `silver.maintenance` (star schema). ADR 0003. Telemetry treatment is configurable
  (`params.yaml → silver.telemetry`).
- **Gold** (`usecase/gold/features.py`) — **one** table `gold.features`, grain
  **(machine_id, 1-hour window)**, built from the three Silver frames. Failure = incident of
  **severity ≥ threshold** (default 4); multi-horizon labels at +6/12/24/48 h + a time-to-failure
  target. **Strictly causal** (features ≤ `t = window_end`; labels strictly after). ADR 0004 / 0010.
- **Cross-source analyses** (`usecase/analyses/`) — joins on `machine_id`/`incident_id`, artefacts
  under `artifacts/analyses/cross_source/`.

### 3.4 Cross-cutting mechanisms
- **Single source registry** (`usecase/sources/registry.py`) — each source declares its facts in
  its runner (`MODEL`, `DUP_KEYS`, `RAW_REF`, `GOLD_ROLE`, `TABLE`, numeric features, hooks),
  aggregated into a `SourceSpec`. Ingestion / Silver / Gold / orchestrator all read the registry
  (no duplicated mapping). ADR (B1).
- **Processing toolkit** (`framework/processing/`) — pure, reusable functions (`dedup`,
  `interpolation` with optional coverage flag, `imputation`, `outliers`, `normalization`,
  `transformation`/encode, `anonymization`) orchestrated by a declarative `ProcessingConfig`
  (`apply_processing`).
- **Per-feature profiling & OK/NOK quality** (`framework/common/profiling.py` + `src/quality.py`)
  — every Bronze/Silver layer produces the same per-feature synthesis + status badge + plots.
- **Lineage & batch traceability** (`framework/lineage/`) — every `run_pipeline` opens a `batch_id`;
  each step writes one row to **`meta.processing_runs`** (rows read/ingested/rejected, status,
  `quality_ok`, git `code_version`, deterministic `output_hash`). `dashboard.py` aggregates per
  batch. ADR 0005.
- **Bulk DB load via COPY** (`framework/db/loader.py`) — ~3× faster than default `to_sql` on the
  wide Gold table; NaN/None → NULL, `""` preserved. ADR 0007.
- **Experiment harness** (`usecase/gold/experiment.py`) — versioned Gold datasets from params
  profiles (`dataset_version` = hash of resolved params, + manifest). ADR 0008/0010.
- **Evaluation metrics** (`usecase/gold/evaluation.py`) — PR-AUC, recall@budget, lead-time, … for
  rare-event scoring. See `MODELING.md`.

---

## 4. Repository layout

```
.
├── CLAUDE.md                  conventions, gotchas, commands (read each session)
├── README.md                  user-facing overview
├── RUNBOOK.md                 run → DVC/Git commit → GitHub push (operational)
├── params.yaml                Gold spec + Silver variants (experiment knobs)
├── pyproject.toml / uv.lock   project metadata, deps, tool config (ruff/black/mypy/pytest)
├── conftest.py                puts the project root on sys.path for tests
├── docker-compose.yml         PostgreSQL service
├── .env(.example)             secrets (ANONYMIZATION_SALT, DB creds)
│
├── src/
│   ├── config.py              KERNEL — paths, DB schemas, column names, constants
│   ├── quality.py             KERNEL — per-feature quality criteria (Check / FEATURE_CHECKS)
│   ├── settings.py            KERNEL — pydantic-settings (salt, DB url) + require_salt()
│   │
│   ├── framework/             GENERIC ENGINE (imports kernel only; never src.usecase.*)
│   │   ├── common/            stage.run_layer, profiling, metrics, reporting, registry,
│   │   │                      overview, processing_summary, env, coherence, synthesis
│   │   ├── processing/        dedup, interpolation, imputation, outliers, normalization,
│   │   │                      transformation, anonymization, pipeline (apply_processing)
│   │   ├── ingestion/         validate.py (parse_ok/parse_reason), stats.py
│   │   ├── lineage/           models (meta.processing_runs), tracker (Batch), quality, dashboard
│   │   ├── db/                engine (settings-driven URL), loader (COPY)
│   │   └── timeutils.py       to_naive_hour (shared time helper)
│   │
│   └── usecase/               THE APPLICATION (imports framework + kernel)
│       ├── orchestrator.py    run_pipeline / run_source_by_name / run_gold
│       ├── sources/           registry.py (SourceSpec) + 1 thin package per source
│       │   ├── incidents/     loader, runner, overview, pipeline
│       │   ├── telemetry/     loader, runner (configurable treatment), overview
│       │   └── machines/      loader, runner (maintenance), referential_runner (dimension),
│       │                      models (SQLite ORM for the .sql dump), overview
│       ├── ingestion/         schemas.py (Pydantic contracts), load.py (ingest Bronze)
│       ├── db/                models_bronze.py (Bronze ORM tables)
│       ├── silver/            refine.py (reject policy + treatments → silver.*)
│       ├── gold/              features.py (builder), stats.py, experiment.py, evaluation.py
│       ├── analyses/          joins, plots, runner (cross-source)
│       └── notebook/          render.py (notebook helpers + shared state)
│
├── scripts/                   predmaint.py (unified CLI) + run_{pipeline,incidents,telemetry,
│                              machines,cross_source}.py (legacy entry points)
├── alembic/                   migrations: 0001 bronze tables, 0002 meta lineage
├── notebooks/                 pipeline.ipynb (3 chapters: BRONZE / SILVER / GOLD)
├── tests/                     pytest: processing, validate, refine policy, gold features,
│                              contracts, dashboard, settings, loader, experiment, evaluation,
│                              silver variants, golden
├── docs/                      ARCHITECTURE, MODELING, GOLD_DATASET_FR, TECHNICAL, adr/
├── .github/workflows/ci.yml   CI (ruff + black + mypy + unit pytest)
├── .claude/                   shared Claude Code config (settings, hooks, skills)
└── artifacts/                 generated runs (gitignored; CSVs via DVC) + gold_experiments/
```

---

## 5. Database

| Schema | Tables | Notes |
|---|---|---|
| `bronze` | `incidents`, `telemetry`, `machine`, `maintenance` | ORM + Alembic; PK `id`; `parse_ok`/`parse_reason`; all rows ingested (invalid flagged) |
| `silver` | `incidents`, `telemetry`, `maintenance` | `to_sql`/COPY replace; `maintenance` enriched with the dimension + `*_code`; `telemetry` carries `was_interpolated` |
| `gold` | `features` | 1 table, grain (machine_id, hour), 253 columns |
| `meta` | `processing_runs` | one row per pipeline step (lineage) |

**Where to run it.** `docker compose` reads the `docker-compose.yml` in the **current directory**,
so always run it from the **project root** — the folder that contains `docker-compose.yml` and
`.env` (here `z:\formation_aelion\project\vs_code`). **Docker Desktop must be running** first
(Windows: launch *Docker Desktop* and wait for the whale icon to be steady). The `.env` file must
exist (the compose file reads `POSTGRES_*` from it).

```powershell
cd z:\formation_aelion\project\vs_code        # project root (where docker-compose.yml lives)
docker compose up -d                          # start PostgreSQL (container predictive_maintenance_db)
docker compose ps                             # status — wait until it shows "healthy"
docker compose logs -f postgres               # (optional) follow the DB logs; Ctrl-C to stop following
uv run alembic upgrade head                   # create/upgrade the bronze + meta schemas

# Lifecycle
docker compose stop                           # stop the container (keeps the data volume)
docker compose down                           # remove the container (data volume `pgdata` is kept)
docker compose down -v                        # remove the container AND wipe the data (fresh start)

# After an ORM change only:
uv run alembic revision -m "msg"              # generate a new migration, then `alembic upgrade head`
```

> First start pulls the `postgres:16-alpine` image (needs network — behind the proxy, Docker
> Desktop uses the system certificates). Data persists in the named volume `pgdata` across
> `up`/`stop`/`down` (only `down -v` deletes it). If port 5432 is busy, change `POSTGRES_PORT` in
> `.env` and reconnect pgAdmin on that port.

If PostgreSQL is unavailable, DB load is skipped with a warning; Silver/Gold still run on files
(`--no-db`). The Gold layer then builds from the in-memory Silver frames.

### 5.1 Inspect the database with pgAdmin

**Where the credentials live.** The DB login/password come from **`.env`** (project root,
gitignored) if it defines `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB`; **otherwise the
defaults apply** — both `docker-compose.yml` (`${POSTGRES_USER:-predictive}` …) and
`src/settings.py` fall back to `predictive` / `predictive` / `predictive_maintenance`.
`.env.example` documents the keys. To see your effective values:
`grep ^POSTGRES_ .env` (no output ⇒ defaults are in effect, i.e. `predictive:predictive`).

> ⚠️ The PostgreSQL password is **fixed at the first initialisation of the `pgdata` volume**.
> Adding/changing `POSTGRES_PASSWORD` in `.env` afterwards has **no effect** until you recreate the
> volume: `docker compose down -v && docker compose up -d` (this **wipes** the DB data).

Connection parameters (the container port is published to the host):

| Field | Value (default) |
|---|---|
| Host | `localhost` |
| Port | `5432` |
| Maintenance DB | `predictive_maintenance` |
| Username | `predictive` |
| Password | `predictive` (or your `.env` `POSTGRES_PASSWORD`) |

**With a desktop pgAdmin 4 already installed:**
1. Start the DB: `docker compose up -d` (and confirm `docker compose ps` shows *healthy*).
2. pgAdmin → right-click **Servers → Register → Server…**
   - **General → Name**: `Predictive Maintenance` (free text).
   - **Connection → Host name/address**: `localhost` · **Port**: `5432` ·
     **Maintenance database**: `predictive_maintenance` · **Username**: `predictive` ·
     **Password**: `predictive` · tick *Save password*.
   - **Save**.
3. Browse: **Servers → Predictive Maintenance → Databases → predictive_maintenance → Schemas**,
   then `bronze` / `silver` / `gold` / `meta` → **Tables**. Right-click a table → *View/Edit Data*,
   or use the **Query Tool** (toolbar) to run SQL (see §5.2).

**No pgAdmin installed? Run it as a container** (add this service to `docker-compose.yml`, then
`docker compose up -d` and open <http://localhost:5050>):

```yaml
  pgadmin:
    image: dpage/pgadmin4
    environment:
      PGADMIN_DEFAULT_EMAIL: admin@example.com
      PGADMIN_DEFAULT_PASSWORD: admin
    ports:
      - "5050:80"
    depends_on:
      - postgres
```
Inside that pgAdmin, register the server with **Host = `postgres`** (the compose service name,
not `localhost`) and the same port/DB/credentials.

> Alternatives: `psql` (`docker compose exec postgres psql -U predictive -d predictive_maintenance`),
> or the VS Code *PostgreSQL* / *Database Client* extensions with the same parameters.

### 5.2 Visualise the lineage (`meta.processing_runs`)

Every `predmaint run` records **one row per step** in `meta.processing_runs`
(`batch_id`, `step`, `layer`, `source`, `input_ref`/`output_ref`, timings, `status`,
`rows_read`/`rows_ingested`/`rows_rejected`, `quality_ok`, `code_version` = git sha,
`output_hash`, `details` JSON).

**From the CLI** (markdown: a per-batch summary table + the latest batch's steps):
```powershell
uv run python scripts/predmaint.py lineage
```

**Web app (Streamlit)** — interactive dashboard reading `meta.processing_runs` (per-batch table,
rows ingested/rejected chart, steps of a selected batch, refresh):
```powershell
uv run streamlit run app/lineage_app.py        # opens http://localhost:8501
```
Requires the DB to be up. On the very first launch Streamlit may ask for an email — just press
Enter to skip (or run headless: `--server.headless true`).

**From the notebook** — the GOLD chapter appendix renders the same via
`src.framework.lineage.dashboard.lineage_dashboard_markdown(engine)` /
`tracker.lineage_markdown(engine)`; `dashboard.plot_batches(runs, out_dir)` writes a per-batch
bar chart (rows ingested vs rejected).

**From pgAdmin (Query Tool)** — ready-to-run SQL:

```sql
-- 1) Full lineage of the most recent run (one row per step, in order)
SELECT step, layer, source, status, rows_read, rows_ingested, rows_rejected,
       quality_ok, duration_s, code_version, output_hash
FROM   meta.processing_runs
WHERE  batch_id = (SELECT batch_id FROM meta.processing_runs
                   ORDER BY started_at DESC LIMIT 1)
ORDER  BY started_at;

-- 2) Per-batch overview (most recent first) — same shape as `predmaint lineage`
SELECT batch_id,
       min(started_at)            AS started_at,
       count(*)                   AS steps,
       sum(rows_ingested)         AS rows_in,
       sum(rows_rejected)         AS rows_rejected,
       bool_and(quality_ok)       AS quality_ok,
       count(*) FILTER (WHERE status <> 'success') AS failed_steps,
       round(sum(duration_s)::numeric, 1)         AS duration_s,
       max(code_version)          AS code_version
FROM   meta.processing_runs
GROUP  BY batch_id
ORDER  BY started_at DESC;

-- 3) Anything that failed or flagged a soft quality issue
SELECT batch_id, step, layer, source, status, quality_ok, details
FROM   meta.processing_runs
WHERE  status <> 'success' OR quality_ok IS FALSE
ORDER  BY started_at DESC;
```

---

## 6. Running everything

### 6.1 Prerequisites (once)
```powershell
cd z:\formation_aelion\project\vs_code
uv sync                                  # (add --native-tls behind the proxy)
Copy-Item .env.example .env              # then set ANONYMIZATION_SALT
docker compose up -d                     # optional (DB); else use --no-db
uv run alembic upgrade head              # if using the DB
```

### 6.2 Unified CLI (`scripts/predmaint.py`) — preferred
```powershell
uv run python scripts/predmaint.py run                  # full pipeline (Bronze→Silver→Gold + cross-source, + DB)
uv run python scripts/predmaint.py run --no-db          # file-only (skip the DB load)
uv run python scripts/predmaint.py source telemetry     # one source (Bronze + Silver); also incidents/machine/machines
uv run python scripts/predmaint.py gold --params experiments/<profile>.yaml   # a versioned Gold dataset
uv run python scripts/predmaint.py gold --no-db         # Gold version from in-memory Silver
uv run python scripts/predmaint.py lineage              # batch lineage (needs DB)
```
Legacy equivalents remain: `scripts/run_pipeline.py [--no-db]`,
`scripts/run_{incidents,telemetry,machines,cross_source}.py`.

The full pipeline writes timestamped run folders (one shared `batch_id`) under
`artifacts/ingestions/<source>/<run>/{bronze,silver}/`, `artifacts/gold/<run>/`, and
`artifacts/analyses/cross_source/<run>/`, plus `meta.processing_runs` when the DB is up.

### 6.3 Experiments — produce N Gold versions
1. Write a profile `experiments/<name>.yaml` with a `gold:` (and/or `silver:`) section overriding
   `params.yaml` (threshold, horizons, windows, split, `baseline_hours`, `failure_refractory_h`).
2. `predmaint gold --params experiments/<name>.yaml` → writes
   `artifacts/gold_experiments/<dataset_version>/{gold.csv, manifest.json}` (params, hash, split
   sizes, label base rates). Silver-level variants (`silver.telemetry`) require a full pipeline
   re-run (they rebuild Silver). See `MODELING.md` for training/evaluation.

### 6.4 Notebook
`notebooks/pipeline.ipynb` (3 chapters: BRONZE / SILVER / GOLD). Select the `.venv` (Python 3.14)
kernel; the Setup cell does `from src.usecase.notebook.render import *`. Don't read the whole
notebook to understand the code — the helpers live in `src/usecase/notebook/render.py`.

### 6.5 Quality gate (before committing)
```powershell
uv run ruff check src scripts tests conftest.py alembic
uv run black --check src scripts tests conftest.py alembic
uv run mypy
uv run pytest -q                  # or: -m "not golden" for the fast unit subset
```

### 6.6 Versioning & publishing (see `RUNBOOK.md`)
`uv run dvc add <…>.csv` → `git add <…>.dvc` → Conventional-Commit → `uv run dvc push` →
`git push`. CI then runs on `master`.

---

## 7. Configuration surfaces

| File | Controls |
|---|---|
| `params.yaml` → `gold.*` | failure threshold, label/memory/trend/event horizons, maintenance windows, split policy, `baseline_hours`, `failure_refractory_h` |
| `params.yaml` → `silver.telemetry` | `interpolate` on/off, `clip_outliers` on/off (dataset variants) |
| `.env` | `ANONYMIZATION_SALT`, `PSEUDONYM_LENGTH`, `POSTGRES_*` |
| `src/config.py` | column names, DB schema names, file paths, domains (kernel) |
| `src/quality.py` | per-feature OK/NOK criteria (kernel) |
| `pyproject.toml` | deps + ruff/black/mypy/pytest config |

---

## 8. Conventions (enforced)
English for all generated content; UTF-8; CSV separator `,`; ISO-8601 dates; `snake_case`
variables / `SCREAMING_SNAKE_CASE` constants; NumPy/Google docstrings; `logging` (no `print` in
production); `ruff` + `black` (line 100) + `mypy` must pass. Conventional Commits. Full rationale
for structuring decisions: [`docs/adr/`](adr/README.md).
