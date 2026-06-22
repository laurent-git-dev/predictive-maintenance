# Claude Code — shared project config

`settings.json` is **versioned** (team-shared); `settings.local.json` is personal (gitignored).

## Permissions (`settings.json` → `permissions.allow`)
Auto-approves **read-only / quality** commands only: `uv run ruff/black/pytest`,
`git status|diff|log|show`, `dvc status|diff`. Anything that writes (commit, push,
`run_pipeline`, `alembic upgrade`, `uv sync`) still asks for confirmation.

## Hooks (`settings.json` → `hooks`, scripts in `.claude/hooks/`)
Each script reads the event JSON on stdin; launched via `uv run python` so `ruff`/`black`/
`pytest` resolve from the project venv. All fail **open** except the guard, which fails safe.

| Event | Script | Effect |
|---|---|---|
| PreToolUse (`Edit\|Write\|MultiEdit\|Bash`) | `guard_paths.py` | **Blocks** writes to `data/raw/` and `.env`, and destructive bash (`rm`/`mv`/`truncate`/redirect) on them. `git add` of `*.dvc` stays allowed. |
| PostToolUse (`Edit\|Write\|MultiEdit`) | `format_python.py` | Auto-runs `ruff check --fix` + `black` on the edited `*.py`. |
| Stop | `check_quality.py` | If uncommitted `*.py` changes exist: `ruff check` + unit tests (`-m "not golden"`). Blocks the stop **once** on failure (`stop_hook_active` guards against loops). |
| Stop / Notification | `printf '\a'` | Terminal bell on task end / when attention is needed. |

Tune or disable any hook by editing `settings.json`. The guard is best-effort (a guard, not a
sandbox); use `settings.local.json` for personal permission additions.
