# organizations (F01)

Legal and operational entities that own all business data.

- Depends on: none (foundation root).
- Models: `Organization`, `Establishment` (unique legal identifier per country, unique establishment code per organization).
- Services: `create_organization_with_default_establishment` (transactional).
- Policies: `can_view_organization` — strict organization isolation.
- Not yet implemented: `LegalEntity`, `Department`, `Team`, `Address`, `LegalProfile`, `FiscalProfile`, `BrandSettings`.
