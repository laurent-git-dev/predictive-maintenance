# Cross-source analysis report — 202606220827

- **Run date**: 2026-06-22 08:27
- **Folder**: `Z:/formation_aelion/project/vs_code/artifacts/analyses/cross_source/202606220827`
- **Sources joined**: incidents · telemetry · machines (maintenance)

## Scope

- Machines profiled: 15
- Reactive maintenances linked to an incident: 1472

## Correlations with incident count (per machine)

| Pair | Pearson r |
|---|---|
| `mean_temperature_c` vs `n_incidents` | 0.86 |
| `mean_pressure_bar` vs `n_incidents` | -0.88 |
| `n_maintenance` vs `n_incidents` | 0.98 |
| `mean_confidence` vs `n_incidents` | -0.40 |

## Produced artifacts

- `machine_profile.csv`
- `1_incidents_vs_maintenance.png`
- `2_reactive_vs_severity.png`
- `3_telemetry_vs_incidents.png`
