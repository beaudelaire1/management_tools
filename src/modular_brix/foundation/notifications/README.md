# notifications (F07)

Business events decoupled from delivery channels and providers.

- Depends on: organizations (F01).
- Models: `MessageTemplate` (variables validated before activation), `Notification` (unique idempotency key per organization), `DeliveryAttempt`.
- Services: `queue_notification` (idempotent only for an identical replay; conflicting payload rejected; user recipients must actively belong to the organization), `deliver_notification` (adapter port, retry cap, failures visible and retryable, no double send), `activate_template`, `render_template`.
- Port: `NotificationChannel` protocol — email/SMS/in-app adapters live in integrations.
- Not yet implemented: `NotificationPreference`, `MessageSuppression`, webhook deliveries, async queue.
