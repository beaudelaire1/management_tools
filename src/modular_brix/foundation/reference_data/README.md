# reference_data (F10)

Shared referentials: countries, currencies, units, tax codes, payment terms.

- Depends on: none.
- Models: `Country`, `Currency`, `Unit`, `TaxCode` (effective dates), `PaymentTerm`.
- Services: `load_initial_reference_data` (idempotent, reproducible), `current_tax_code` (expired values never proposed; history stays readable).
- Not yet implemented: `Language`, `Calendar`, `Holiday`, `ReasonCode`, update import.
