# ADR 0010 — Gold feature enrichment, leakage fix and train/val/test split

**Status:** Accepted · supersedes part of [0004](0004-gold-single-table-no-leakage.md)

## Context
Business goal: best possible Gold dataset for failure prediction. An audit of the builder found
a temporal **leak**, **missing** high-value features, and no evaluation split.

## Decision
- **Leakage fix:** the per-machine z-score `*_z_machine` used the machine's **full** series
  mean/std (peeking at the future). Replaced by `*_z_hist` = z vs the **expanding** (causal)
  mean/std up to & including `t`. All features remain strictly ≤ `t`.
- **New feature groups** (all causal): **machine** (static dimension: criticality / model / line
  / location codes, capacities, `machine_age_years` at `t`), **load** (`utilization` =
  pieces ÷ hourly capacity, `over_capacity_flag`, `utilization_mean_24h`), **recurrence**
  (`fail_count_<h>`, `fail_count_cum`, `fail_hours_since_last`), **calendar** (cyclical hour /
  day-of-week, `is_weekend`), plus `failure_now` (flag to exclude ongoing-failure rows).
  Second lot added **physics** (`power_proxy` = V×rpm + 24h mean, `temp_pressure_ratio`,
  `efficiency_pieces_per_krpm`, `co_anomaly_24h` = #measures with |z₂₄ₕ|>3), **drift** vs the
  machine's **healthy baseline** (median of its first `baseline_hours`, causal — NaN before the
  window closes), and **coverage** (`interpolated_now`, `interp_frac_24h`, `hours_since_real_obs`
  — fed by a new `was_interpolated` flag written in Silver telemetry). Table 216 → **251** columns.
- **Split:** `split_set` is assigned from `params.yaml` (`gold.split`): `temporal` (global cut,
  test = most recent period; default), `by_machine`, or `none`. Enables honest evaluation
  (no random shuffle across autocorrelated rows).

## Consequences
- The reference golden hash changes (216→239 cols) — updated deliberately; new tests pin the
  causal `z_hist` (no future leak) and the temporal split.
- Machine context comes from the dimension denormalised in `silver.maintenance`; a machine with
  no maintenance row would get NaN machine features (rare; documented).
- Coverage features required a Silver change: `interpolate_by_group(flag_col=…)` writes
  `was_interpolated` into `silver.telemetry` (its golden hash changes accordingly).
- These knobs (threshold, horizons, windows, split, `baseline_hours`) are the basis for dataset
  experiments ([0008](0008-gold-params-no-dvc-dag.md)).
