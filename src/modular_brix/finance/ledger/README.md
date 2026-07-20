# ledger (C08)

Double-entry general ledger with periods, validation and reversal.

- Entries balance or are rejected; validation allocates a continuous chronological number per journal/year (F09) and freezes the entry at ORM level; the only correction is a linked reversal; ledger, balances and trial balance only count validated entries; locked periods and closed years reject entries.
- Limits: PostgreSQL immutability triggers for entries and multi-currency remain to implement.
