# machines — silver dataset report

> Silver layer · per-feature understanding.

## Dataset at a glance

| Indicator | Value |
|---|---|
| Layer | silver |
| Rows | 1562 |
| Columns | 23 |
| Unique machines | 15 |
| Missing values (total) | 90 |

**How to read this report.** Each feature shows a type-aware synthesis (range, missing, spread, skew, outliers, top values…) and, for numeric features, a boxplot across machines and its distribution (histogram + KDE).

## Per-feature analysis

### maintenance_id (<span style="color:green">OK</span>)

- **dtype** int64 · **count** 1562 · **unique** 1562 · **missing** 0 (0.0%)

### machine_id (<span style="color:green">OK</span>)

- **dtype** str · **count** 1562 · **unique** 15 · **missing** 0 (0.0%)
- **most frequent** `MACH-03` (271, 17.35%)
- **distinct values**: MACH-01, MACH-02, MACH-03, MACH-04, MACH-05, MACH-06, MACH-07, MACH-08, MACH-09, MACH-10, MACH-11, MACH-12, MACH-13, MACH-14, MACH-15

### maintenance_at (<span style="color:green">OK</span>)

- **dtype** datetime64[us, UTC] · **count** 1562 · **unique** 1474 · **missing** 0 (0.0%)
- **range** 2025-06-02 04:42 → 2026-06-09 02:29 (span 371 days)

### maintenance_type (<span style="color:green">OK</span>)

- **dtype** str · **count** 1562 · **unique** 2 · **missing** 0 (0.0%)
- **distinct values**: proactive (5.8%), reactive (94.2%)

### action_type (<span style="color:green">OK</span>)

- **dtype** str · **count** 1562 · **unique** 3 · **missing** 0 (0.0%)
- **distinct values**: changement_programme (5.8%), changement_suite_panne (1.6%), intervention_corrective (92.6%)

### component (<span style="color:green">OK</span>)

- **dtype** str · **count** 1562 · **unique** 12 · **missing** 0 (0.0%)
- **most frequent** `roulement axe principal` (463, 29.64%)
- **distinct values**: capteur pression, capteur température, convoyeur sortie, courroie moteur, filtre hydraulique, joint hydraulique, outillage presse, relais sécurité, roulement axe principal, système sécurité, transmission, variateur vitesse

![component](3.1_count_component.png)

### description (<span style="color:green">OK</span>)

- **dtype** str · **count** 1562 · **unique** 42 · **missing** 0 (0.0%)
- **most frequent** `Remplacement capteur + recalibration zéro` (249, 15.94%)

![description](3.2_count_description.png)

### related_incident_id (<span style="color:green">OK</span>)

- **dtype** str · **count** 1472 · **unique** 1057 · **missing** 90 (5.76%)
- **most frequent** `INC-000037` (3, 0.2%)

### duration_hours (<span style="color:green">OK</span>)

- **dtype** float64 · **count** 1562 · **unique** 282 · **missing** 0 (0.0%)
- **range** 1.0 → 8.0 (span 7.0) · **Q1/median/Q3** 2.0 / 2.41 / 2.82
- **mean** 2.482 · **std** 0.731 · **skew** 2.105

**Outliers** — flagged values per method:

| method | normal band | below — n (range) | above — n (range) |
|---|---|---|---|
| IQR (k=1.5) | [0.77, 4.05] | 0 — | 39 [4.06, 8.0] |
| z-score (k=3) | [0.288, 4.676] | 0 — | 22 [4.71, 8.0] |

**Outliers by machine** (IQR k=1.5 and z-score k=3, fences recomputed per machine):

| machine | n | IQR below | IQR above | z-score below | z-score above |
|---|---|---|---|---|---|
| MACH-01 | 187 | 0 | 0 | 0 | 0 |
| MACH-02 | 44 | 0 | 1 | 0 | 1 |
| MACH-03 | 271 | 0 | 13 | 0 | 5 |
| MACH-04 | 52 | 0 | 2 | 0 | 2 |
| MACH-05 | 100 | 0 | 3 | 0 | 1 |
| MACH-06 | 65 | 0 | 1 | 0 | 1 |
| MACH-07 | 43 | 0 | 1 | 0 | 1 |
| MACH-08 | 108 | 0 | 3 | 0 | 2 |
| MACH-09 | 86 | 0 | 6 | 0 | 1 |
| MACH-10 | 74 | 0 | 2 | 0 | 1 |
| MACH-11 | 64 | 0 | 2 | 0 | 2 |
| MACH-12 | 54 | 0 | 2 | 0 | 1 |
| MACH-13 | 260 | 0 | 0 | 0 | 0 |
| MACH-14 | 66 | 0 | 0 | 0 | 0 |
| MACH-15 | 88 | 0 | 3 | 0 | 3 |
| **total** | 1562 | 0 | 39 | 0 | 21 |

![duration_hours](1.1_box_duration_hours.png)

![duration_hours](2.1_dist_duration_hours.png)

![duration_hours](8.1_cum_duration_hours.png)

### commissioning_date (<span style="color:green">OK</span>)

- **dtype** datetime64[us] · **count** 1562 · **unique** 15 · **missing** 0 (0.0%)
- **range** 2019-07-23 00:00 → 2025-05-25 00:00 (span 2133 days)
- **distinct values**: 2019-07-23 00:00:00, 2019-12-30 00:00:00, 2021-04-16 00:00:00, 2021-05-12 00:00:00, 2021-10-21 00:00:00, 2022-01-01 00:00:00, 2022-03-16 00:00:00, 2022-09-15 00:00:00, 2023-01-07 00:00:00, 2023-01-15 00:00:00, 2023-10-18 00:00:00, 2024-02-21 00:00:00, 2024-03-11 00:00:00, 2024-09-07 00:00:00, 2025-05-25 00:00:00

### max_daily_capacity (<span style="color:green">OK</span>)

- **dtype** int64 · **count** 1562 · **unique** 15 · **missing** 0 (0.0%)
- **range** 750.0 → 1428.0 (span 678.0) · **Q1/median/Q3** 838.0 / 1027.0 / 1380.0
- **mean** 1070.836 · **std** 246.185 · **skew** 0.225
- **distinct values**: 1027, 1056, 1158, 1191, 1351, 1380, 1405, 1428, 750, 770, 778, 800, 838, 907, 984

### max_hourly_capacity_pieces (<span style="color:green">OK</span>)

- **dtype** int64 · **count** 1562 · **unique** 15 · **missing** 0 (0.0%)
- **range** 47.0 → 89.0 (span 42.0) · **Q1/median/Q3** 52.0 / 64.0 / 86.0
- **mean** 66.93 · **std** 15.328 · **skew** 0.229
- **distinct values**: 47, 48, 49, 50, 52, 57, 62, 64, 66, 72, 74, 84, 86, 88, 89

### model (<span style="color:green">OK</span>)

- **dtype** str · **count** 1562 · **unique** 4 · **missing** 0 (0.0%)
- **most frequent** `InduPress-X2` (635, 40.65%)
- **distinct values**: InduPress-X1, InduPress-X2, InduPress-X3, InduPress-Z1

![model](3.6_count_model.png)

### production_line (<span style="color:green">OK</span>)

- **dtype** str · **count** 1562 · **unique** 3 · **missing** 0 (0.0%)
- **most frequent** `Ligne-B` (583, 37.32%)
- **distinct values**: Ligne-A, Ligne-B, Ligne-C

![production_line](3.4_count_production_line.png)

### location (<span style="color:green">OK</span>)

- **dtype** str · **count** 1562 · **unique** 3 · **missing** 0 (0.0%)
- **most frequent** `Atelier-3` (669, 42.83%)
- **distinct values**: Atelier-1, Atelier-2, Atelier-3

![location](3.5_count_location.png)

### criticality (<span style="color:green">OK</span>)

- **dtype** str · **count** 1562 · **unique** 3 · **missing** 0 (0.0%)
- **most frequent** `MEDIUM` (782, 50.06%)
- **distinct values**: HIGH, LOW, MEDIUM

![criticality](3.3_count_criticality.png)

### maintenance_type_code

- **dtype** Int64 · **count** 1562 · **unique** 2 · **missing** 0 (0.0%)
- **distinct values**: 0 (5.8%), 1 (94.2%)

### action_type_code

- **dtype** Int64 · **count** 1562 · **unique** 3 · **missing** 0 (0.0%)
- **range** 0.0 → 2.0 (span 2.0) · **Q1/median/Q3** 2.0 / 2.0 / 2.0
- **mean** 1.869 · **std** 0.479 · **skew** -3.506

**Outliers** — flagged values per method:

| method | normal band | below — n (range) | above — n (range) |
|---|---|---|---|
| IQR (k=1.5) | [2.0, 2.0] | 115 [0.0, 1.0] | 0 — |
| z-score (k=3) | [0.432, 3.306] | 90 [0.0, 0.0] | 0 — |

**Outliers by machine** (IQR k=1.5 and z-score k=3, fences recomputed per machine):

| machine | n | IQR below | IQR above | z-score below | z-score above |
|---|---|---|---|---|---|
| MACH-01 | 187 | 8 | 0 | 6 | 0 |
| MACH-02 | 44 | 7 | 0 | 0 | 0 |
| MACH-03 | 271 | 7 | 0 | 7 | 0 |
| MACH-04 | 52 | 8 | 0 | 0 | 0 |
| MACH-05 | 100 | 9 | 0 | 6 | 0 |
| MACH-06 | 65 | 7 | 0 | 6 | 0 |
| MACH-07 | 43 | 7 | 0 | 0 | 0 |
| MACH-08 | 108 | 8 | 0 | 6 | 0 |
| MACH-09 | 86 | 9 | 0 | 6 | 0 |
| MACH-10 | 74 | 8 | 0 | 6 | 0 |
| MACH-11 | 64 | 8 | 0 | 0 | 0 |
| MACH-12 | 54 | 8 | 0 | 0 | 0 |
| MACH-13 | 260 | 6 | 0 | 6 | 0 |
| MACH-14 | 66 | 6 | 0 | 6 | 0 |
| MACH-15 | 88 | 9 | 0 | 6 | 0 |
| **total** | 1562 | 115 | 0 | 61 | 0 |
- **distinct values**: 0, 1, 2

### component_code

- **dtype** Int64 · **count** 1562 · **unique** 12 · **missing** 0 (0.0%)
- **range** 0.0 → 11.0 (span 11.0) · **Q1/median/Q3** 1.0 / 5.0 / 8.0
- **mean** 5.154 · **std** 3.655 · **skew** -0.02

**Outliers** — flagged values per method:

| method | normal band | below — n (range) | above — n (range) |
|---|---|---|---|
| IQR (k=1.5) | [-9.5, 18.5] | 0 — | 0 — |
| z-score (k=3) | [-5.812, 16.119] | 0 — | 0 — |

**Outliers by machine** (IQR k=1.5 and z-score k=3, fences recomputed per machine):

| machine | n | IQR below | IQR above | z-score below | z-score above |
|---|---|---|---|---|---|
| MACH-01 | 187 | 0 | 0 | 0 | 0 |
| MACH-02 | 44 | 0 | 0 | 0 | 0 |
| MACH-03 | 271 | 0 | 0 | 0 | 0 |
| MACH-04 | 52 | 0 | 0 | 0 | 0 |
| MACH-05 | 100 | 0 | 0 | 0 | 0 |
| MACH-06 | 65 | 0 | 0 | 0 | 0 |
| MACH-07 | 43 | 0 | 0 | 0 | 0 |
| MACH-08 | 108 | 0 | 0 | 0 | 0 |
| MACH-09 | 86 | 0 | 0 | 0 | 0 |
| MACH-10 | 74 | 0 | 0 | 0 | 0 |
| MACH-11 | 64 | 0 | 0 | 0 | 0 |
| MACH-12 | 54 | 0 | 0 | 0 | 0 |
| MACH-13 | 260 | 0 | 0 | 0 | 0 |
| MACH-14 | 66 | 0 | 0 | 0 | 0 |
| MACH-15 | 88 | 0 | 0 | 0 | 0 |
| **total** | 1562 | 0 | 0 | 0 | 0 |
- **distinct values**: 0, 1, 10, 11, 2, 3, 4, 5, 6, 7, 8, 9

### criticality_code

- **dtype** Int64 · **count** 1562 · **unique** 3 · **missing** 0 (0.0%)
- **range** 0.0 → 2.0 (span 2.0) · **Q1/median/Q3** 1.0 / 1.0 / 2.0
- **mean** 1.114 · **std** 0.698 · **skew** -0.159

**Outliers** — flagged values per method:

| method | normal band | below — n (range) | above — n (range) |
|---|---|---|---|
| IQR (k=1.5) | [-0.5, 3.5] | 0 — | 0 — |
| z-score (k=3) | [-0.979, 3.207] | 0 — | 0 — |

**Outliers by machine** (IQR k=1.5 and z-score k=3, fences recomputed per machine):

| machine | n | IQR below | IQR above | z-score below | z-score above |
|---|---|---|---|---|---|
| MACH-01 | 187 | 0 | 0 | 0 | 0 |
| MACH-02 | 44 | 0 | 0 | 0 | 0 |
| MACH-03 | 271 | 0 | 0 | 0 | 0 |
| MACH-04 | 52 | 0 | 0 | 0 | 0 |
| MACH-05 | 100 | 0 | 0 | 0 | 0 |
| MACH-06 | 65 | 0 | 0 | 0 | 0 |
| MACH-07 | 43 | 0 | 0 | 0 | 0 |
| MACH-08 | 108 | 0 | 0 | 0 | 0 |
| MACH-09 | 86 | 0 | 0 | 0 | 0 |
| MACH-10 | 74 | 0 | 0 | 0 | 0 |
| MACH-11 | 64 | 0 | 0 | 0 | 0 |
| MACH-12 | 54 | 0 | 0 | 0 | 0 |
| MACH-13 | 260 | 0 | 0 | 0 | 0 |
| MACH-14 | 66 | 0 | 0 | 0 | 0 |
| MACH-15 | 88 | 0 | 0 | 0 | 0 |
| **total** | 1562 | 0 | 0 | 0 | 0 |
- **distinct values**: 0, 1, 2

### production_line_code

- **dtype** Int64 · **count** 1562 · **unique** 3 · **missing** 0 (0.0%)
- **range** 0.0 → 2.0 (span 2.0) · **Q1/median/Q3** 0.0 / 1.0 / 2.0
- **mean** 0.901 · **std** 0.786 · **skew** 0.176

**Outliers** — flagged values per method:

| method | normal band | below — n (range) | above — n (range) |
|---|---|---|---|
| IQR (k=1.5) | [-3.0, 5.0] | 0 — | 0 — |
| z-score (k=3) | [-1.456, 3.258] | 0 — | 0 — |

**Outliers by machine** (IQR k=1.5 and z-score k=3, fences recomputed per machine):

| machine | n | IQR below | IQR above | z-score below | z-score above |
|---|---|---|---|---|---|
| MACH-01 | 187 | 0 | 0 | 0 | 0 |
| MACH-02 | 44 | 0 | 0 | 0 | 0 |
| MACH-03 | 271 | 0 | 0 | 0 | 0 |
| MACH-04 | 52 | 0 | 0 | 0 | 0 |
| MACH-05 | 100 | 0 | 0 | 0 | 0 |
| MACH-06 | 65 | 0 | 0 | 0 | 0 |
| MACH-07 | 43 | 0 | 0 | 0 | 0 |
| MACH-08 | 108 | 0 | 0 | 0 | 0 |
| MACH-09 | 86 | 0 | 0 | 0 | 0 |
| MACH-10 | 74 | 0 | 0 | 0 | 0 |
| MACH-11 | 64 | 0 | 0 | 0 | 0 |
| MACH-12 | 54 | 0 | 0 | 0 | 0 |
| MACH-13 | 260 | 0 | 0 | 0 | 0 |
| MACH-14 | 66 | 0 | 0 | 0 | 0 |
| MACH-15 | 88 | 0 | 0 | 0 | 0 |
| **total** | 1562 | 0 | 0 | 0 | 0 |
- **distinct values**: 0, 1, 2

### location_code

- **dtype** Int64 · **count** 1562 · **unique** 3 · **missing** 0 (0.0%)
- **range** 0.0 → 2.0 (span 2.0) · **Q1/median/Q3** 0.0 / 1.0 / 2.0
- **mean** 1.08 · **std** 0.878 · **skew** -0.156

**Outliers** — flagged values per method:

| method | normal band | below — n (range) | above — n (range) |
|---|---|---|---|
| IQR (k=1.5) | [-3.0, 5.0] | 0 — | 0 — |
| z-score (k=3) | [-1.554, 3.714] | 0 — | 0 — |

**Outliers by machine** (IQR k=1.5 and z-score k=3, fences recomputed per machine):

| machine | n | IQR below | IQR above | z-score below | z-score above |
|---|---|---|---|---|---|
| MACH-01 | 187 | 0 | 0 | 0 | 0 |
| MACH-02 | 44 | 0 | 0 | 0 | 0 |
| MACH-03 | 271 | 0 | 0 | 0 | 0 |
| MACH-04 | 52 | 0 | 0 | 0 | 0 |
| MACH-05 | 100 | 0 | 0 | 0 | 0 |
| MACH-06 | 65 | 0 | 0 | 0 | 0 |
| MACH-07 | 43 | 0 | 0 | 0 | 0 |
| MACH-08 | 108 | 0 | 0 | 0 | 0 |
| MACH-09 | 86 | 0 | 0 | 0 | 0 |
| MACH-10 | 74 | 0 | 0 | 0 | 0 |
| MACH-11 | 64 | 0 | 0 | 0 | 0 |
| MACH-12 | 54 | 0 | 0 | 0 | 0 |
| MACH-13 | 260 | 0 | 0 | 0 | 0 |
| MACH-14 | 66 | 0 | 0 | 0 | 0 |
| MACH-15 | 88 | 0 | 0 | 0 | 0 |
| **total** | 1562 | 0 | 0 | 0 | 0 |
- **distinct values**: 0, 1, 2

### model_code

- **dtype** Int64 · **count** 1562 · **unique** 4 · **missing** 0 (0.0%)
- **range** 0.0 → 3.0 (span 3.0) · **Q1/median/Q3** 1.0 / 1.0 / 2.0
- **mean** 1.204 · **std** 0.916 · **skew** 0.333

**Outliers** — flagged values per method:

| method | normal band | below — n (range) | above — n (range) |
|---|---|---|---|
| IQR (k=1.5) | [-0.5, 3.5] | 0 — | 0 — |
| z-score (k=3) | [-1.544, 3.951] | 0 — | 0 — |

**Outliers by machine** (IQR k=1.5 and z-score k=3, fences recomputed per machine):

| machine | n | IQR below | IQR above | z-score below | z-score above |
|---|---|---|---|---|---|
| MACH-01 | 187 | 0 | 0 | 0 | 0 |
| MACH-02 | 44 | 0 | 0 | 0 | 0 |
| MACH-03 | 271 | 0 | 0 | 0 | 0 |
| MACH-04 | 52 | 0 | 0 | 0 | 0 |
| MACH-05 | 100 | 0 | 0 | 0 | 0 |
| MACH-06 | 65 | 0 | 0 | 0 | 0 |
| MACH-07 | 43 | 0 | 0 | 0 | 0 |
| MACH-08 | 108 | 0 | 0 | 0 | 0 |
| MACH-09 | 86 | 0 | 0 | 0 | 0 |
| MACH-10 | 74 | 0 | 0 | 0 | 0 |
| MACH-11 | 64 | 0 | 0 | 0 | 0 |
| MACH-12 | 54 | 0 | 0 | 0 | 0 |
| MACH-13 | 260 | 0 | 0 | 0 | 0 |
| MACH-14 | 66 | 0 | 0 | 0 | 0 |
| MACH-15 | 88 | 0 | 0 | 0 | 0 |
| **total** | 1562 | 0 | 0 | 0 | 0 |
- **distinct values**: 0, 1, 2, 3



## Notes for business teams

- High `pct_missing` or `n_outliers_iqr` flags columns to clean in Silver (imputation / outliers, configured in src/sources/registry.py).
- Compare Bronze vs Silver to see the effect of the treatment.
