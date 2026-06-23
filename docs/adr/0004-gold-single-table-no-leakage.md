# ADR 0004 — One Gold table at (machine, hour); leakage-safe labels

**Status:** Accepted

## Context
Gold feeds model training. We must pick a grain, a target definition, and guarantee no temporal
leakage between features and labels.

## Decision
A **single** table `gold.features` at grain **(machine_id, 1-hour window)**, built from the three
Silver frames. Decision instant `t = window_end`: backward features (memory / trend / anomaly /
context) look up to **and including** the current hour; labels look **strictly after** `t`. A
**failure = incident of severity ≥ 4** (parametrable, [0008](0008-gold-params-no-dvc-dag.md));
labels are multi-horizon (+6/12/24/48 h). A future window extending past the machine's last
observed hour is **censored → NaN** (row kept, not dropped).

## Consequences
- One training-ready table (no per-source Gold), simple to consume; ~216 columns.
- No leakage by construction; censored labels are explicit (NaN) rather than fake negatives.
- Telemetry is the hourly spine; incidents/maintenance are aggregated onto it.
- Unit-tested for unique grain, feature groups and no-leakage labels (`tests/test_gold_features.py`).
