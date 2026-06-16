# Run report — 202606162112

- **Source**: `Z:\formation_aelion\project\vs_code\data\raw\incidents.csv`
- **Run date**: 2026-06-16 21:12
- **Folder**: `Z:/formation_aelion/project/vs_code/artifacts/ingestions/incidents/202606162112`

## Quality metrics (source data)

| Metric | Value |
|---|---|
| Number of rows | 900 |
| Number of columns | 19 |
| Unique machines | 15 |
| Missing values (total) | 59 |

### Missing values per column

| Column | Missing |
|---|---|
| `comment` | 59 |

## Anonymisation

- `operator_name` → Truncated HMAC-SHA256 to 16 characters (secret salt)
- `operator_badge` → Opaque identifier OP_xxxxxx (HMAC-SHA256)
- `comment` → Kept + comment_pii_flag column (manual review recommended)

## Reporting confidence index

`confidence_index = number of active signals / total number of signals`

| Statistic | Value |
|---|---|
| Mean | 0.113 |
| Median | 0.1111 |
| Min | 0.1111 |
| Max | 0.2222 |

## Produced artifacts

- `incidents_anonymized.csv`
- `1.1_dist_incidents_day.png`
- `1.2_dist_incidents_week.png`
- `1.3_dist_incidents_shift.png`
- `2.1_hist_incidents_machine.png`
- `2.2_hist_incidents_operator.png`
- `2.3_hist_incidents_signal.png`
- `2.4_hist_incidents_confidence.png`
- `3.1_corr_severity_signals.png`
- `3.2_corr_severity_comment.png`
- `dataset_report.md`
