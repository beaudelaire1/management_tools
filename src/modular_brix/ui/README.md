# ui (F12)

Neutral, accessible server-rendered UI library.

- Depends on: accounts (F02), organizations (F01).
- Models: `SavedView` (per user/view, upsert), `UserTablePreference`.
- Templates: `ui/base.html` (skip link, landmarks, lang attribute), `ui/components/table.html` (caption, `scope="col"`, accessible empty state).
- Services: `save_view`, `save_table_preference`.
- The optional `modular_brix.portal` app provides the complete authenticated organization shell, responsive design
  tokens, generic resource screens, accessible forms, and the quote-to-cash command interface.
- Not yet implemented: `SavedFilter`, `NavigationConfiguration`, HTMX partials catalog, kanban/calendar components.
