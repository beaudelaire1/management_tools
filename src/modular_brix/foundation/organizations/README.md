# organizations (F01)

Legal and operational entities that own all business data.

- Depends on: none (foundation root).
- Models: `Organization`, `Establishment`, `LegalEntity`, `Department`, `Team`, `Address`, `LegalProfile`, `FiscalProfile`, `BrandSettings`.
- Services: `create_organization_with_default_establishment`, `archive_organization` (archive without delete — historical references intact).
- Policies: `can_view_organization` — strict organization isolation.
