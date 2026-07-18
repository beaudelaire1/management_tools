# sequences (F09)

Transactional document numbering.

- Depends on: organizations (F01).
- Models: `SequenceCounter` — unique per (organization, code, period).
- Services: `allocate_number` — atomic allocation under `SELECT FOR UPDATE`, no duplicates under concurrency (verified by a PostgreSQL concurrency test in CI); `format_reference`.
- Not yet implemented: reserved numbers, format configuration UI, anomaly log (`SequenceEvent`).
