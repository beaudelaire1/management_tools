# purchasing (G06)

Purchase requests, supplier orders and goods receipts.

- Services: `submit_request`, `approve_request` (requester/approver separation), `create_order_from_request` (idempotent, numbered via F09), `receive_goods` (partial receipts capped by the ordered remainder).
- Limits: supplier quotations comparison, budget-threshold policies and supplier evaluation remain to implement.
