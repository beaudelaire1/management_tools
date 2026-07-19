# reports (P13)

Reproducible reports over read-only datasets.

- Depends on: permissions (F03), billing (C01).
- Models: `Report` (registered dataset key only), `ReportRun` (parameters + timestamp stored).
- Services: `create_report` (unknown dataset rejected), `run_report` — permission-checked (unauthorized recipient blocked), reproducible output, every run recorded with its parameters.
- Not yet implemented: scheduling, recipients, PDF/CSV/XLSX exports, volume limits.
