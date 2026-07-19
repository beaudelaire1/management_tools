# ui (F12)

Neutral, accessible server-rendered UI library.

- Depends on: accounts (F02), organizations (F01).
- Models: `SavedView` (per user/view, upsert), `UserTablePreference`.
- Templates: `ui/base.html` (skip link, landmarks, lang attribute), `ui/components/table.html` (caption, `scope="col"`, accessible empty state).
- Services: `save_view`, `save_table_preference`.
- Not yet implemented: `SavedFilter`, `NavigationConfiguration`, HTMX partials catalog, theme tokens, kanban/calendar components.
