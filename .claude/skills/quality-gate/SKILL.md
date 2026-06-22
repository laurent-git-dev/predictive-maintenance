---
name: quality-gate
description: Run the full quality gate (ruff + black + pytest incl. golden) and report a concise verdict. Use when the user wants to lint/format/test the codebase or verify it before a commit. Manual counterpart of the Stop hook (which runs unit tests only).
---

# Quality gate

Runs lint, format check and the full test suite, then reports PASS/FAIL per stage.

Scope linters to the Python sources (the notebook has known, out-of-scope ruff findings):

```bash
uv run ruff check src scripts tests conftest.py
uv run black --check src scripts tests conftest.py
uv run pytest -q                 # 30 tests incl. 10 golden (need data/raw; skipped if absent)
```

## Reporting

- Give a one-line verdict per stage (ruff / black / pytest) with counts.
- On ruff/black failure: offer to auto-fix — `uv run ruff check --fix src scripts tests conftest.py`
  then `uv run black src scripts tests conftest.py` — then re-run.
- On pytest failure: show the failing test name(s) and the assertion; if a **golden** test fails,
  it means Bronze/Silver/Gold output changed — confirm with the user whether that change is
  intended before updating the frozen constants in `tests/test_golden.py`.
- Golden tests are skipped when `data/raw/` is absent; say so rather than reporting a false pass.

Fast unit-only pass (matches the Stop hook): `uv run pytest -q -m "not golden"`.
