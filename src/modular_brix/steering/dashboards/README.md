# dashboards (P01)

Role-scoped steering dashboards.

- Depends on: indicators (P02), permissions (F03).
- Models: `Dashboard`, `DashboardWidget` (authorized catalog: kpi | trend | list).
- Services: `add_widget` (catalog and organization consistency enforced), `get_widget_data` — access requires an active membership with read permission in the dashboard organization; every decision is logged.
- Not yet implemented: sections, sharing, caching, presentation mode, HTMX progressive loading.
