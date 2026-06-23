# ADR 0008 — Gold spec in params.yaml; no DVC DAG

**Status:** Accepted

## Context
Reusability goal: re-target the use case (failure threshold, horizons, windows) without code
edits, and possibly express the pipeline as a DVC `dvc.yaml` DAG.

## Decision
Externalise the Gold spec to **`params.yaml`** (`gold.*`: `failure_severity_min`, label /
memory / trend / event horizons, maintenance windows), read by `load_gold_params`. Defaults
reproduce the reference table exactly (golden hash unchanged). **No `dvc.yaml` DAG** is added.

## Consequences
- The spec is tunable in one declarative file; the code reads parameters, not constants.
- A DVC file-dependency DAG is a poor fit for a **DB-chained** pipeline ([0001](0001-medallion-db-chained.md)):
  intermediate state lives in PostgreSQL, and artifact CSVs are already tracked via `dvc add`.
  Orchestration is handled by the `predmaint` CLI + skills instead.
- Changing `params.yaml` away from defaults will (intentionally) change the Gold output and the
  golden hash — update the frozen values when the change is deliberate.
