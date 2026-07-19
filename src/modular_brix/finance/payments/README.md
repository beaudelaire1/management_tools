# payments (C02)

Payment registration and allocation to invoices.

- Depends on: billing (C01), parties (G01).
- Models: `Payment` (unique idempotency key per organization — webhook-safe), `PaymentAllocation` (positive amounts, DB checks).
- Services: `register_payment` (same external event and payload twice = one payment; conflicting replay rejected), `allocate_payment` — never exceeds the unallocated payment amount nor the invoice remaining due; organization, party, and currency consistency enforced; `payment_unallocated`.
- Not yet implemented: refunds, deposits, unidentified payments, provider adapters.
