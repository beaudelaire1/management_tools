# sales (G04 + G05)

Quotes, versions, acceptance, orders, and deliveries.

- Depends on: parties (G01), sequences (F09); totals via `modular_brix.common.money`.
- Models: `Quote` (versioned, frozen once sent), `QuoteLine`, `SalesOrder` (one per quote), `SalesOrderLine` (DB check: delivered <= ordered), `Delivery`, `DeliveryLine`.
- Services: `create_quote` (sequence number), `add_quote_line` (draft only), `send_quote` (totals computed once, centrally), `revise_quote` (modification after sending = new version), `accept_quote` (proof required), `convert_quote_to_order` (idempotent), `record_delivery` (capped at ordered quantity, auto-fulfillment).
- Not yet implemented: quote sections/options, PDF rendering, returns, customer acceptance portal.
