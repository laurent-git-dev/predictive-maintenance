# RUNBOOK — pipeline run, DVC/Git commit, GitHub push

Operational guide to autonomously: **(1)** produce a full pipeline run, **(2)** commit the
result locally (DVC data + Git), and **(3)** push the code to GitHub.

> Working shell: **PowerShell** in VS Code (Windows 11). All commands below are PowerShell.
> Run them from the project root: `z:\formation_aelion\project\vs_code`.

---

## 0. Prerequisites (once)

```powershell
cd z:\formation_aelion\project\vs_code

# .env must exist with at least ANONYMIZATION_SALT
#   (otherwise: Copy-Item .env.example .env  then fill it in)
# Start PostgreSQL so the database-load step runs
#   (if it is down, that step is skipped with a warning — Bronze/Silver still run)
docker compose up -d
```

### Corporate proxy (Avast TLS interception)

This machine intercepts TLS, which breaks default certificate validation. Workarounds:

- **Git** (already set in this repo's *local* config, nothing to redo):
  ```powershell
  git config http.sslBackend schannel
  git config http.schannelCheckRevoke false
  ```
- **uv / dvc** network operations: add `--native-tls` (or set `$env:UV_SYSTEM_CERTS = "true"`).
  The DVC remote is **local** (`C:/Users/lpottier/dvc-storage/...`), so `dvc push` needs no network.
- **curl** downloads: add `--ssl-no-revoke`.

---

## 1. Run the full pipeline

```powershell
# Unified CLI (preferred):
uv run python scripts/predmaint.py run            # full pipeline (+ DB load)
uv run python scripts/predmaint.py run --no-db    # skip the database load
uv run python scripts/predmaint.py source telemetry [--no-db]   # a single source
uv run python scripts/predmaint.py lineage        # latest batch lineage (needs DB)

# Equivalent legacy scripts (still available):
# uv run python scripts/run_pipeline.py [--no-db]
```

Creates new timestamped run folders (one shared `batch_id` per run) under
`artifacts/ingestions/<source>/<run>/{bronze,silver}/`, `artifacts/gold/<run>/` and
`artifacts/analyses/cross_source/<run>/`, and updates each `runs_registry.json`.

---

## 2. Commit locally (DVC data + Git)

```powershell
# (Optional) Keep only the latest run per source — a clean "reference run"
Get-ChildItem artifacts/ingestions, artifacts/analyses -Directory | ForEach-Object {
  Get-ChildItem $_.FullName -Directory | Sort-Object Name | Select-Object -SkipLast 1 |
    Remove-Item -Recurse -Force
}
# Prune the registries (keep only runs whose folder still exists)
Get-ChildItem artifacts -Recurse -Filter runs_registry.json | ForEach-Object {
  $j = Get-Content $_.FullName -Raw | ConvertFrom-Json
  $j.runs = @($j.runs | Where-Object { Test-Path $_.folder })
  ($j | ConvertTo-Json -Depth 10) | Set-Content $_.FullName -Encoding utf8
}

# Version the data CSVs through DVC (every ingestion CSV without a .dvc sidecar)
Get-ChildItem artifacts/ingestions -Recurse -Filter *.csv |
  Where-Object { -not (Test-Path "$($_.FullName).dvc") } |
  ForEach-Object { uv run dvc add $_.FullName }

# Stage everything else (plots .png, reports .md, .dvc files, registries, code) and commit
git add -A
git status -s          # visual check before committing
git commit -m "feat(data): regenerate reference run <YYYYMMDDHHMM>"

# Push the data blobs to the local DVC remote
uv run dvc push
```

**Key points**
- Data CSVs are **never** in Git (git-ignored) — only their `.dvc` sidecars are tracked.
- `dvc push` often prints *"Everything is up to date"* when the source data is unchanged
  (the pipeline is deterministic → identical md5s).
- Commit messages follow **Conventional Commits** (`feat(...)`, `fix(...)`, `docs:`, `refactor(...)`).

---

## 3. Push to GitHub (remote `origin` already configured)

```powershell
git push               # master already tracks origin/master
```

Repository: <https://github.com/laurent-git-dev/predictive-maintenance>

**If the `gh` auth ever expires** (`gh auth status` no longer says "Logged in"):

```powershell
# Classic token with scopes 'repo','read:org' from https://github.com/settings/tokens
"<YOUR_TOKEN>" | gh auth login --hostname github.com --git-protocol https --with-token
gh auth setup-git
```

> `gh` (v2.95.0) is installed at `%USERPROFILE%\.local\bin\gh.exe`, which is on the user PATH.

---

## All-in-one (copy/paste)

```powershell
cd z:\formation_aelion\project\vs_code
docker compose up -d
uv run python scripts/run_pipeline.py
Get-ChildItem artifacts/ingestions -Recurse -Filter *.csv |
  Where-Object { -not (Test-Path "$($_.FullName).dvc") } |
  ForEach-Object { uv run dvc add $_.FullName }
git add -A
git commit -m "feat(data): new pipeline run"
uv run dvc push
git push
```
