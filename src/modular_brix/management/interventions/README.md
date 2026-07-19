# interventions (G09)

Work orders, interventions, stock consumption and customer signatures.

- `consume_item` is idempotent and tied one-to-one to its stock movement: stock is decremented exactly once.
- Closing requires a report; customer signatures are immutable.
- Limits: checklists, photos and mobile/degraded mode remain to implement.
