# telemetry — silver dataset report

> Silver layer · per-feature understanding.

## Dataset at a glance

| Indicator | Value |
|---|---|
| Layer | silver |
| Rows | 135626 |
| Columns | 7 |
| Unique machines | 15 |
| Missing values (total) | 0 |

**How to read this report.** Each feature shows a type-aware synthesis (range, missing, spread, skew, outliers, top values…) and, for numeric features, a boxplot across machines and its distribution (histogram + KDE).

## Per-feature analysis

### machine_id (<span style="color:green">OK</span>)

- **dtype** str · **count** 135626 · **unique** 15 · **missing** 0 (0.0%)
- **most frequent** `MACH-03` (9054, 6.68%)
- **distinct values**: MACH-01, MACH-02, MACH-03, MACH-04, MACH-05, MACH-06, MACH-07, MACH-08, MACH-09, MACH-10, MACH-11, MACH-12, MACH-13, MACH-14, MACH-15

### timestamp (<span style="color:red">NOK</span>)

- **dtype** datetime64[us] · **count** 135626 · **unique** 8952 · **missing** 0 (0.0%)
- **range** 2025-06-01 00:00 → 2026-06-08 23:00 (span 372 days)

**Per-machine timestamp QC** (hourly series):

| machine | rows | duplicate timestamps | missing hours |
|---|---|---|---|
| MACH-01 | 9033 | 81 | 0 |
| MACH-02 | 9042 | 90 | 0 |
| MACH-03 | 9054 | 102 | 0 |
| MACH-04 | 9042 | 90 | 0 |
| MACH-05 | 9033 | 81 | 0 |
| MACH-06 | 9049 | 97 | 0 |
| MACH-07 | 9034 | 82 | 0 |
| MACH-08 | 9053 | 101 | 0 |
| MACH-09 | 9048 | 96 | 0 |
| MACH-10 | 9043 | 91 | 0 |
| MACH-11 | 9040 | 88 | 0 |
| MACH-12 | 9031 | 79 | 0 |
| MACH-13 | 9043 | 91 | 0 |
| MACH-14 | 9044 | 92 | 0 |
| MACH-15 | 9037 | 85 | 0 |
| **total** | 135626 | 1346 | 0 |
- **NOK reason**: duplicate timestamp(s) for a machine

### temperature_c (<span style="color:green">OK</span>)

- **dtype** float64 · **count** 135626 · **unique** 18056 · **missing** 0 (0.0%)
- **range** 32.654 → 63.642 (span 30.988) · **Q1/median/Q3** 44.275 / 48.055 / 52.022
- **mean** 48.17 · **std** 5.187 · **skew** 0.076

**Outliers** — flagged values per method:

| method | normal band | below — n (range) | above — n (range) |
|---|---|---|---|
| IQR (k=1.5) | [32.654, 63.642] | 0 — | 0 — |
| z-score (k=3) | [32.609, 63.731] | 0 — | 0 — |

![temperature_c](1.1_box_temperature_c.png)

![temperature_c](2.1_dist_temperature_c.png)

### pressure_bar (<span style="color:green">OK</span>)

- **dtype** float64 · **count** 135626 · **unique** 9255 · **missing** 0 (0.0%)
- **range** 194.692 → 205.072 (span 10.38) · **Q1/median/Q3** 198.584 / 199.866 / 201.179
- **mean** 199.842 · **std** 1.861 · **skew** -0.15

**Outliers** — flagged values per method:

| method | normal band | below — n (range) | above — n (range) |
|---|---|---|---|
| IQR (k=1.5) | [194.692, 205.072] | 0 — | 0 — |
| z-score (k=3) | [194.26, 205.425] | 0 — | 0 — |

![pressure_bar](1.2_box_pressure_bar.png)

![pressure_bar](2.2_dist_pressure_bar.png)

### voltage_mean_v (<span style="color:green">OK</span>)

- **dtype** float64 · **count** 135626 · **unique** 3914 · **missing** 0 (0.0%)
- **range** 221.35 → 233.83 (span 12.48) · **Q1/median/Q3** 226.03 / 227.42 / 229.15
- **mean** 227.622 · **std** 2.271 · **skew** 0.24

**Outliers** — flagged values per method:

| method | normal band | below — n (range) | above — n (range) |
|---|---|---|---|
| IQR (k=1.5) | [221.35, 233.83] | 0 — | 0 — |
| z-score (k=3) | [220.809, 234.435] | 0 — | 0 — |

![voltage_mean_v](1.3_box_voltage_mean_v.png)

![voltage_mean_v](2.3_dist_voltage_mean_v.png)

### rotation_mean_rpm (<span style="color:green">OK</span>)

- **dtype** float64 · **count** 135626 · **unique** 26747 · **missing** 0 (0.0%)
- **range** 1467.141 → 1712.717 (span 245.576) · **Q1/median/Q3** 1559.232 / 1590.37 / 1620.626
- **mean** 1589.3 · **std** 43.205 · **skew** -0.114

**Outliers** — flagged values per method:

| method | normal band | below — n (range) | above — n (range) |
|---|---|---|---|
| IQR (k=1.5) | [1467.141, 1712.717] | 0 — | 0 — |
| z-score (k=3) | [1459.686, 1718.915] | 0 — | 0 — |

![rotation_mean_rpm](1.4_box_rotation_mean_rpm.png)

![rotation_mean_rpm](2.4_dist_rotation_mean_rpm.png)

### pieces_produced (<span style="color:green">OK</span>)

- **dtype** int64 · **count** 135626 · **unique** 115 · **missing** 0 (0.0%)
- **range** 0.0 → 114.0 (span 114.0) · **Q1/median/Q3** 28.0 / 49.0 / 68.0
- **mean** 49.533 · **std** 24.573 · **skew** 0.09

**Outliers** — flagged values per method:

| method | normal band | below — n (range) | above — n (range) |
|---|---|---|---|
| IQR (k=1.5) | [-32.0, 128.0] | 0 — | 0 — |
| z-score (k=3) | [-24.186, 123.253] | 0 — | 0 — |

![pieces_produced](1.5_box_pieces_produced.png)

![pieces_produced](2.5_dist_pieces_produced.png)

![pieces_produced](6.1_ts_pieces_produced.png)

![pieces_produced](6.2_ts_pieces_produced.png)



## Notes for business teams

- High `pct_missing` or `n_outliers_iqr` flags columns to clean in Silver (imputation / outliers, configured in src/sources/registry.py).
- Compare Bronze vs Silver to see the effect of the treatment.
