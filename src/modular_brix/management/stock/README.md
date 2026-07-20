# stock (G07)

Warehouses, append-only stock movements, reservations, inventory counts.

- Stock levels are always computed from movements; movements can never be edited or deleted.
- `reserve_stock` locks the warehouse row so reservations never exceed availability; inventory gaps are materialized by justified adjustment movements.
- Limits: lots/serial numbers, valuation methods and reorder rules remain to implement.
