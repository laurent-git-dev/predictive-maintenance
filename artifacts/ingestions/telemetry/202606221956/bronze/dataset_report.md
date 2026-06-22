# telemetry — bronze dataset report

> Bronze layer · per-feature understanding.

## Dataset at a glance

| Indicator | Value |
|---|---|
| Layer | bronze |
| Rows | 135626 |
| Columns | 7 |
| Unique machines | 15 |
| Missing values (total) | 2847 |

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

### temperature_c (<span style="color:red">NOK</span>)

- **dtype** float64 · **count** 134732 · **unique** 18312 · **missing** 894 (0.66%)
- **range** 32.0 → 80.0 (span 48.0) · **Q1/median/Q3** 44.248 / 48.055 / 52.054
- **mean** 48.183 · **std** 5.253 · **skew** 0.181

**Outliers** — flagged values per method:

| method | normal band | below — n (range) | above — n (range) |
|---|---|---|---|
| IQR (k=1.5) | [32.539, 63.763] | 2 [32.0, 32.0] | 277 [63.769, 80.0] |
| z-score (k=3) | [32.423, 63.943] | 2 [32.0, 32.0] | 271 [63.955, 80.0] |

**Outliers by machine** (IQR k=1.5 and z-score k=3, fences recomputed per machine):

| machine | n | IQR below | IQR above | z-score below | z-score above |
|---|---|---|---|---|---|
| MACH-01 | 8989 | 5 | 23 | 2 | 20 |
| MACH-02 | 8967 | 17 | 2 | 8 | 2 |
| MACH-03 | 8999 | 8 | 23 | 4 | 22 |
| MACH-04 | 8993 | 11 | 25 | 3 | 25 |
| MACH-05 | 8971 | 2 | 41 | 1 | 36 |
| MACH-06 | 9006 | 0 | 0 | 0 | 0 |
| MACH-07 | 8983 | 0 | 6 | 0 | 7 |
| MACH-08 | 8977 | 0 | 23 | 0 | 27 |
| MACH-09 | 8983 | 0 | 26 | 0 | 30 |
| MACH-10 | 9018 | 0 | 11 | 0 | 14 |
| MACH-11 | 8930 | 0 | 23 | 0 | 29 |
| MACH-12 | 8973 | 0 | 17 | 0 | 20 |
| MACH-13 | 8982 | 0 | 11 | 0 | 15 |
| MACH-14 | 8987 | 0 | 29 | 0 | 32 |
| MACH-15 | 8974 | 0 | 26 | 0 | 25 |
| **total** | 134732 | 43 | 286 | 18 | 304 |
- **NOK reason**: no empty value

![temperature_c](1.1_box_temperature_c.png)

![temperature_c](2.1_dist_temperature_c.png)

### pressure_bar (<span style="color:red">NOK</span>)

- **dtype** float64 · **count** 134631 · **unique** 10708 · **missing** 995 (0.73%)
- **range** 159.982 → 215.814 (span 55.832) · **Q1/median/Q3** 198.573 / 199.866 / 201.19
- **mean** 199.77 · **std** 2.372 · **skew** -4.16

**Outliers** — flagged values per method:

| method | normal band | below — n (range) | above — n (range) |
|---|---|---|---|
| IQR (k=1.5) | [194.648, 205.114] | 1287 [159.982, 194.646] | 242 [205.117, 215.814] |
| z-score (k=3) | [192.654, 206.887] | 929 [159.982, 192.653] | 129 [206.903, 215.814] |

**Outliers by machine** (IQR k=1.5 and z-score k=3, fences recomputed per machine):

| machine | n | IQR below | IQR above | z-score below | z-score above |
|---|---|---|---|---|---|
| MACH-01 | 8967 | 117 | 18 | 74 | 4 |
| MACH-02 | 8999 | 124 | 58 | 46 | 31 |
| MACH-03 | 9002 | 297 | 20 | 136 | 6 |
| MACH-04 | 8989 | 89 | 17 | 33 | 4 |
| MACH-05 | 8977 | 156 | 29 | 90 | 3 |
| MACH-06 | 8977 | 102 | 49 | 66 | 20 |
| MACH-07 | 8942 | 46 | 22 | 35 | 13 |
| MACH-08 | 9024 | 58 | 15 | 52 | 14 |
| MACH-09 | 8934 | 53 | 13 | 43 | 10 |
| MACH-10 | 8958 | 77 | 17 | 63 | 11 |
| MACH-11 | 8984 | 21 | 3 | 22 | 5 |
| MACH-12 | 8973 | 80 | 0 | 64 | 0 |
| MACH-13 | 8934 | 120 | 0 | 96 | 0 |
| MACH-14 | 8991 | 40 | 2 | 30 | 0 |
| MACH-15 | 8980 | 76 | 19 | 56 | 7 |
| **total** | 134631 | 1456 | 282 | 906 | 128 |
- **NOK reason**: no empty value

![pressure_bar](1.2_box_pressure_bar.png)

![pressure_bar](2.2_dist_pressure_bar.png)

### voltage_mean_v (<span style="color:green">OK</span>)

- **dtype** float64 · **count** 135626 · **unique** 4392 · **missing** 0 (0.0%)
- **range** 220.9 → 242.0 (span 21.1) · **Q1/median/Q3** 226.03 / 227.42 / 229.15
- **mean** 227.631 · **std** 2.304 · **skew** 0.377

**Outliers** — flagged values per method:

| method | normal band | below — n (range) | above — n (range) |
|---|---|---|---|
| IQR (k=1.5) | [221.35, 233.83] | 19 [220.9, 221.33] | 625 [233.84, 242.0] |
| z-score (k=3) | [220.719, 234.543] | 0 — | 365 [234.556, 242.0] |

**Outliers by machine** (IQR k=1.5 and z-score k=3, fences recomputed per machine):

| machine | n | IQR below | IQR above | z-score below | z-score above |
|---|---|---|---|---|---|
| MACH-01 | 9033 | 52 | 115 | 1 | 73 |
| MACH-02 | 9042 | 91 | 47 | 19 | 29 |
| MACH-03 | 9054 | 89 | 135 | 8 | 92 |
| MACH-04 | 9042 | 92 | 47 | 24 | 28 |
| MACH-05 | 9033 | 48 | 149 | 4 | 82 |
| MACH-06 | 9049 | 15 | 25 | 3 | 19 |
| MACH-07 | 9034 | 3 | 5 | 1 | 5 |
| MACH-08 | 9053 | 0 | 83 | 0 | 75 |
| MACH-09 | 9048 | 0 | 26 | 0 | 29 |
| MACH-10 | 9043 | 0 | 21 | 0 | 26 |
| MACH-11 | 9040 | 0 | 13 | 0 | 16 |
| MACH-12 | 9031 | 0 | 9 | 0 | 18 |
| MACH-13 | 9043 | 1 | 121 | 0 | 100 |
| MACH-14 | 9044 | 3 | 53 | 1 | 39 |
| MACH-15 | 9037 | 23 | 67 | 1 | 49 |
| **total** | 135626 | 417 | 916 | 62 | 680 |

![voltage_mean_v](1.3_box_voltage_mean_v.png)

![voltage_mean_v](2.3_dist_voltage_mean_v.png)

### rotation_mean_rpm (<span style="color:red">NOK</span>)

- **dtype** float64 · **count** 134668 · **unique** 27474 · **missing** 958 (0.71%)
- **range** 1100.0 → 1900.0 (span 800.0) · **Q1/median/Q3** 1558.994 / 1590.37 / 1620.832
- **mean** 1589.205 · **std** 45.949 · **skew** -0.367

**Outliers** — flagged values per method:

| method | normal band | below — n (range) | above — n (range) |
|---|---|---|---|
| IQR (k=1.5) | [1466.237, 1713.589] | 486 [1100.0, 1466.224] | 354 [1713.66, 1900.0] |
| z-score (k=3) | [1451.359, 1727.051] | 350 [1100.0, 1451.263] | 276 [1727.567, 1900.0] |

**Outliers by machine** (IQR k=1.5 and z-score k=3, fences recomputed per machine):

| machine | n | IQR below | IQR above | z-score below | z-score above |
|---|---|---|---|---|---|
| MACH-01 | 8956 | 144 | 82 | 30 | 50 |
| MACH-02 | 8989 | 253 | 26 | 59 | 3 |
| MACH-03 | 8974 | 246 | 92 | 59 | 37 |
| MACH-04 | 8937 | 175 | 58 | 16 | 30 |
| MACH-05 | 8979 | 135 | 58 | 24 | 28 |
| MACH-06 | 8978 | 69 | 21 | 33 | 11 |
| MACH-07 | 8971 | 29 | 30 | 20 | 21 |
| MACH-08 | 8984 | 19 | 5 | 20 | 5 |
| MACH-09 | 9009 | 24 | 5 | 28 | 8 |
| MACH-10 | 8944 | 13 | 7 | 17 | 9 |
| MACH-11 | 9001 | 4 | 8 | 5 | 11 |
| MACH-12 | 8997 | 4 | 9 | 5 | 12 |
| MACH-13 | 9006 | 90 | 62 | 65 | 47 |
| MACH-14 | 8991 | 16 | 15 | 8 | 12 |
| MACH-15 | 8952 | 81 | 22 | 23 | 14 |
| **total** | 134668 | 1302 | 500 | 412 | 298 |
- **NOK reason**: no empty value

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

**Outliers by machine** (IQR k=1.5 and z-score k=3, fences recomputed per machine):

| machine | n | IQR below | IQR above | z-score below | z-score above |
|---|---|---|---|---|---|
| MACH-01 | 9033 | 0 | 0 | 0 | 0 |
| MACH-02 | 9042 | 0 | 0 | 0 | 0 |
| MACH-03 | 9054 | 0 | 0 | 0 | 0 |
| MACH-04 | 9042 | 0 | 0 | 0 | 0 |
| MACH-05 | 9033 | 0 | 0 | 0 | 0 |
| MACH-06 | 9049 | 0 | 0 | 0 | 0 |
| MACH-07 | 9034 | 0 | 0 | 0 | 0 |
| MACH-08 | 9053 | 0 | 0 | 0 | 0 |
| MACH-09 | 9048 | 0 | 0 | 0 | 0 |
| MACH-10 | 9043 | 0 | 0 | 0 | 0 |
| MACH-11 | 9040 | 0 | 0 | 0 | 0 |
| MACH-12 | 9031 | 0 | 0 | 0 | 0 |
| MACH-13 | 9043 | 0 | 0 | 0 | 0 |
| MACH-14 | 9044 | 0 | 0 | 0 | 0 |
| MACH-15 | 9037 | 0 | 0 | 0 | 0 |
| **total** | 135626 | 0 | 0 | 0 | 0 |

![pieces_produced](1.5_box_pieces_produced.png)

![pieces_produced](2.5_dist_pieces_produced.png)

![pieces_produced](6.1_ts_pieces_produced.png)

![pieces_produced](6.2_ts_pieces_produced.png)



## Notes for business teams

- High `pct_missing` or `n_outliers_iqr` flags columns to clean in Silver (imputation / outliers, configured in src/sources/registry.py).
- Compare Bronze vs Silver to see the effect of the treatment.
