# data_transfer (F11)

Controlled, traceable import and export.

- Depends on: organizations (F01).
- Models: `ImportJob` (all-or-nothing mode), `ImportRow` (row-by-row report), `ExportJob`.
- Services: `create_import_job`, `apply_import` — validation before any write; in all-or-nothing mode a single invalid row rejects the whole batch with zero writes; `run_export` — the row provider is scoped by organization id.
- Not yet implemented: `ImportMapping`, `ExportTemplate`, `DataQualityRule`, temp-file encryption, deduplication.
