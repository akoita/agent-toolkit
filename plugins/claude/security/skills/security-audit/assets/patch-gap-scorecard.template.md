# Vulnerability patch-gap scorecard

## Reporting frame

- Repository/component: `<scope>`
- Reporting window: `<start UTC>` to `<end UTC>`
- Population: `<which severities, releases, and deployment/adoption targets>`
- Percentile method: `<nearest-rank or documented interpolation>`
- Closed findings included: `<n>`
- Open findings reported separately: `<n and age summary>`
- Exclusions/not-applicable stages: `<count and reasons>`

Do not include open intervals in closed-item percentiles. For a small sample,
list individual durations and mark p90 `insufficient sample` rather than
reporting false precision.

## Lifecycle duration

| Interval | n | p50 | p90 | Oldest open age | Notes |
| --- | ---: | ---: | ---: | ---: | --- |
| Discovery → triage | `<n>` | `<duration>` | `<duration>` | `<duration>` | `<notes>` |
| Discovery → reproduction | `<n>` | `<duration>` | `<duration>` | `<duration>` | `<notes>` |
| Reproduction → fix | `<n>` | `<duration>` | `<duration>` | `<duration>` | `<notes>` |
| Fix → release | `<n>` | `<duration>` | `<duration>` | `<duration>` | `<notes>` |
| Release → deployed/adopted | `<n>` | `<duration>` | `<duration>` | `<duration>` | `<notes>` |
| Discovery → deployed/adopted | `<n>` | `<duration>` | `<duration>` | `<duration>` | `<notes>` |

## Finding-level audit trail

| Finding | Severity | Discovered | Triaged | Reproduced | Fixed | Released | Deployed/adopted | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `<id>` | `<severity>` | `<UTC>` | `<UTC>` | `<UTC/N/A>` | `<UTC>` | `<UTC/N/A>` | `<UTC/N/A>` | `<state>` |

## Interpretation and action

- Largest delay and its verified cause: `<evidence>`
- Findings waiting for an owner or decision: `<ids>`
- Release/adoption bottleneck: `<evidence>`
- Structural mitigation follow-ups: `<ids and owners>`
- Next review date and human owner: `<date, owner>`

These metrics diagnose delay; they do not override severity, exploit activity,
safe rollout, or human approval.
