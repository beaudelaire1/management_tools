# audit (F04)

Append-only business audit trail.

- Depends on: organizations (F01).
- Models: `AuditEvent` — UTC timestamps, actor, context JSON; `save()` on an existing row and `delete()` raise (append-only at the ORM layer).
- Services: `record_audit_event`.
- Known limits: queryset-level `update()` bypasses model guards — a database trigger is planned for PostgreSQL; audit-access logging and secret masking not yet implemented.
