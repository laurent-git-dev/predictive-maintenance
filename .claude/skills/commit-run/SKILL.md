---
name: commit-run
description: Version a pipeline run and commit it — DVC-add the data CSVs, git commit (Conventional Commits), dvc push, git push. Use when the user wants to save/commit/push a reference run or pipeline results. Encodes RUNBOOK §2–3.
---

# Commit a pipeline run (DVC data + Git + push)

Encodes RUNBOOK §2–3. **Data CSVs never go in Git** (gitignored) — only their `.dvc` sidecars.
The DVC remote is **local** (`dvc push` needs no network). Git is already configured for the
proxy (`http.sslBackend=schannel`).

> The PreToolUse guard blocks writes to `data/raw/` and `.env`; staging `*.dvc` is allowed.

## 1. (Optional) keep only the latest run per source — a clean reference run

bash:
```bash
for d in artifacts/ingestions/*/ artifacts/analyses/*/; do
  ls -1d "$d"*/ 2>/dev/null | sort | head -n -1 | xargs -r rm -rf
done
```
(PowerShell equivalent with registry pruning is in RUNBOOK §2.)

## 2. DVC-add the data CSVs (those without a `.dvc` sidecar)

```bash
find artifacts/ingestions -name '*.csv' | while read -r f; do
  [ -f "$f.dvc" ] || uv run dvc add "$f"
done
```

## 3. Commit (Conventional Commits) + DVC push + Git push

```bash
git add -A
git status -s          # visual check first
git commit -m "feat(data): regenerate reference run <YYYYMMDDHHMM>"
uv run dvc push        # local remote; often "Everything is up to date" (deterministic pipeline)
git push               # master tracks origin/master
```

## Notes

- Commit prefixes: `feat(...)`, `fix(...)`, `docs:`, `refactor(...)`, `chore(...)`. End with the
  `Co-Authored-By` trailer when requested.
- If `gh`/git auth expired, see RUNBOOK §3 (token login via `gh auth login --with-token`).
- Confirm with the user before `git push` (outward-facing action).
