# catalog (G03)

Products, services, and dated pricing.

- Depends on: organizations (F01).
- Models: `CatalogItem` (default tax rate, archivable), `Price` (Decimal, effective dates, currency).
- Services: `set_price`, `resolve_price` — historical price reproducible at any date; archived items cannot be priced.
- Not yet implemented: `PriceList`, `PricingRule`, `DiscountRule`, `Bundle`, price explanation trace.
