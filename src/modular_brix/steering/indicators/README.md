# indicators (P02)

Auditable KPI definitions and values.

- Depends on: organizations (F01).
- Models: `IndicatorDefinition` (unit, source, frequency, owner mandatory; versioned formula code), `IndicatorValue` (origin: manual | computed | import; inputs stored).
- Services: `create_indicator` (invalid formula cannot be published), `compute_indicator_value` (deterministic: same period + same inputs = same value), `record_manual_value`, `latest_value`.
- Not yet implemented: scorecards, thresholds/alerts, import origin pipeline.
