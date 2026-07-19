# audit (F04)

Append-only business audit trail.

- Depends on: organizations (F01).
- Models: `AuditEvent` — UTC timestamps, actor, context JSON; `save()` on an existing row and `delete()` raise (append-only at the ORM layer).
- Services: `record_audit_event`.
- Known limits: append-only is enforced at ORM level everywhere and by a PostgreSQL trigger (migration 0002) at database level; audit-access logging and secret masking not yet implemented.
