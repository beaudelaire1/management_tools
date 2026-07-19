# payments (C02)

Payment registration and allocation to invoices.

- Depends on: billing (C01), parties (G01).
- Models: `Payment` (unique idempotency key per organization — webhook-safe), `PaymentAllocation` (positive amounts, DB checks).
- Services: `register_payment` (same external event twice = one payment), `allocate_payment` — never exceeds the unallocated payment amount nor the invoice remaining due; organization and currency consistency enforced; `payment_unallocated`.
- Not yet implemented: refunds, deposits, unidentified payments, provider adapters.
