# contracts (G12)

Contracts, frozen signed versions, renewals and idempotent subscriptions.

- Signed versions are immutable; renewal is an explicit dated act; termination preserves history.
- `bill_subscription_period` creates exactly one draft invoice per contract and period.
- Limits: proration, automatic renewals and multi-party contracts remain to implement.
