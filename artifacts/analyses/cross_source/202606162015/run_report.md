# Cross-source analysis report — 202606162015

- **Run date**: 2026-06-16 20:15
- **Folder**: `Z:/formation_aelion/project/vs_code/artifacts/analyses/cross_source/202606162015`
- **Sources joined**: incidents · telemetry · machines (maintenance)

## Scope

- Machines profiled: 15
- Reactive maintenances linked to an incident: 25

## Correlations with incident count (per machine)

| Pair | Pearson r |
|---|---|
| `mean_temperature_c` vs `n_incidents` | 0.17 |
| `mean_pressure_bar` vs `n_incidents` | -0.09 |
| `n_maintenance` vs `n_incidents` | -0.03 |
| `mean_confidence` vs `n_incidents` | 0.24 |

## Produced artifacts

- `machine_profile.csv`
- `1_incidents_vs_maintenance.png`
- `2_reactive_vs_severity.png`
- `3_telemetry_vs_incidents.png`
