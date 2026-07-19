# banking (C06)

Bank accounts, idempotent statement imports and audited reconciliation.

- Re-importing identical content returns the stored statement; inconsistent balances are refused; one-to-many matching is capped by the transaction amount; unmatching requires a reason and leaves an audit event.
- Limits: categorization rules, suggestions and internal transfer mirroring remain to implement.
