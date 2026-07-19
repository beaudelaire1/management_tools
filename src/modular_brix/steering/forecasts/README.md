# forecasts (P05 + P06)

Deterministic forecasts and side-effect-free scenario comparison.

- Depends on: organizations (F01); money helpers.
- Models: `Forecast`, `ForecastVersion` (dated, assumptions stored), `ForecastLine`.
- Services: `build_forecast_version` — deterministic recompute, assumptions exported with the result, never writes to source tables; `compare_scenarios` (P06 baseline) — pure comparison, nothing booked.
- Not yet implemented: rolling forecast UI, variance-per-line explanation, scenario cloning/sensitivity tests.
