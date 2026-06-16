# Incident dataset — synthesis report

> Run `202606161715` · shareable summary for business teams. The data is anonymised:
> operators are pseudonymised and cannot be re-identified.

## Dataset at a glance

| Indicator | Value |
|---|---|
| Reporting period | 2025-06-01 → 2026-06-08 |
| Number of incidents | 900 |
| Unique machines | 15 |
| Unique operators (pseudonymised) | 10 |
| Signals tracked | 9 |
| Missing values (total) | 59 |
| Mean confidence index | 0.113 |

**How to read this report.** Each incident records the machine, the shift, the
severity and the set of *signals* (anomaly types prefixed by `type_`) that fired.
The **confidence index** of an incident is the share of signals active at once:
an incident corroborated by several signals is considered more reliable than one
relying on a single isolated signal.

## 1. Temporal distributions

### Incident distribution per day
![Incident distribution per day](1.1_dist_incidents_day.png)

### Incident distribution per week
![Incident distribution per week](1.2_dist_incidents_week.png)

### Incident distribution per shift
![Incident distribution per shift](1.3_dist_incidents_shift.png)

## 2. Incident histograms

### Incidents per machine
![Incidents per machine](2.1_hist_incidents_machine.png)

### Incidents per operator (pseudonymised)
![Incidents per operator (pseudonymised)](2.2_hist_incidents_operator.png)

### Incidents per signal
![Incidents per signal](2.3_hist_incidents_signal.png)

### Incidents per confidence index
![Incidents per confidence index](2.4_hist_incidents_confidence.png)

## 3. Correlations

### Correlation: severity / signals
![Correlation: severity / signals](3.1_corr_severity_signals.png)

### Correlation: severity / comment presence
![Correlation: severity / comment presence](3.2_corr_severity_comment.png)

## Notes for business teams

- Machines and shifts concentrating the most incidents (sections 1 & 2) are
  natural priorities for preventive maintenance.
- The severity / signals correlation (3.1) highlights which signals tend to go
  with more severe incidents.
- Incidents with a low confidence index (single signal) may deserve a closer
  manual review.
