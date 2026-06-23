# Modeling & evaluation protocol

How to train and **honestly** evaluate a failure-prediction model on the Gold dataset. The
pipeline produces the data; the model lives in your own training code. This doc fixes the
protocol so experiments are comparable.

## Dataset
- Grain: one row per `(machine_id, 1-hour window)`; decision instant `t = window_end`.
- Targets: `label_failure_next_{6h,12h,24h,48h}` (binary, multi-horizon) and `label_ttf_hours`
  (+ `label_ttf_censored`) for time-to-failure / survival.
- All features are strictly causal (≤ `t`). Build versions with `predmaint gold --params <profile>`
  (each writes `artifacts/gold_experiments/<version>/gold.csv` + `manifest.json`).

## Splitting (no leakage)
- Use the provided **`split_set`** (`gold.split` in `params.yaml`): `temporal` (default — test is
  the most recent period) or `by_machine` (cross-machine generalisation). **Never** shuffle
  randomly: rows are autocorrelated and a single failure spans many positive rows.
- For cross-validation, use **time-series CV** (expanding window) and/or **group CV by machine** —
  not plain k-fold.
- **Drop censored rows** (NaN label) per horizon before training/eval (`evaluation_frame`).
- Optionally drop `failure_now == 1` rows (the machine is already failing) to predict onset.

## Imbalance
Positives are ~0.9% (6h) … ~7% (48h) — see each version's `manifest.json` `label_positive_rate`.
Handle it: `class_weight`/`scale_pos_weight`, focal loss, or resampling **on the train split
only**; and **calibrate** probabilities (isotonic/Platt) if you threshold them.

## Metrics (`src/usecase/gold/evaluation.py`)
Accuracy is meaningless here. Report, on the **test** split:
- **PR-AUC** (`pr_auc`) — the primary metric for rare events.
- **Recall at an alert budget** (`recall_at_top_k`, e.g. top 1% / 5% scored rows) — operationally
  "if we can inspect k% of machine-hours, what share of failures do we catch?".
- **Precision / recall / F1** at a chosen threshold (`precision_recall_at_threshold`).
- **Lead time** (`lead_time_hours` with `label_ttf_hours`) — median hours of warning at true-positive
  alerts; more warning = more actionable.
- `evaluate(y_true, y_score, ttf_hours)` bundles these.

## Suggested experiment loop
1. Pick a profile (threshold / horizons / windows / split / `failure_refractory_h`) → build a Gold
   version (`predmaint gold --params`). The `dataset_version` + `manifest.json` make it reproducible.
2. Train one model per horizon (or multi-output) on `split_set == "train"`, tune on `"val"`.
3. Evaluate on `"test"` with the metrics above; compare versions by PR-AUC / recall@budget / lead-time.
4. Keep the manifest with the model artefacts so each result is traceable to its dataset version.
