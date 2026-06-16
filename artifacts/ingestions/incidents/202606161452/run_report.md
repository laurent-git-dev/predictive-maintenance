# Run report — 202606161452

- **Source**: `data\raw\incidents.csv`
- **Run date**: 2026-06-16 14:52
- **Folder**: `Z:/formation_aelion/project/vs_code/artifacts/ingestions/incidents/202606161452`

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
- `dist_incidents_day.png`
- `dist_incidents_week.png`
- `dist_incidents_shift.png`
- `hist_signals_machine.png`
- `corr_incidents_signals.png`
