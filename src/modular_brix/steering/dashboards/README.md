# dashboards (P01)

Role-scoped steering dashboards.

- Depends on: indicators (P02), permissions (F03).
- Models: `Dashboard`, `DashboardWidget` (authorized catalog: kpi | trend | list).
- Services: `add_widget` (catalog enforced), `get_widget_data` — a widget never bypasses data permissions (read action checked and logged).
- Not yet implemented: sections, sharing, caching, presentation mode, HTMX progressive loading.
