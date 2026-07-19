# receivables (C03)

Aging balance, reminders, and disputes.

- Depends on: billing (C01), payments (C02).
- Models: `Dispute` (open/resolved), `Reminder` (escalating levels).
- Services: `aging_buckets` (reproducible: current / 1-30 / 31-60 / 60+), `send_due_reminders` — paid invoices leave the cycle, invoices under an open dispute are suspended; `open_dispute` (reason required), `resolve_dispute`.
- Not yet implemented: `ReminderPolicy` configuration, payment promises, penalties computation, collection cases.
