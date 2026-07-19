# portal

Authenticated, organization-scoped, server-rendered interface for the installed Modular Brix domains.

- Lists and details are driven by an explicit resource registry and remain organization-bound.
- Core quote-to-cash commands use the transactional domain services rather than writing models directly.
- Read, create, and validation actions are checked through the permission policy.
- Templates are accessible, responsive, progressive-enhancement friendly, and require no SPA runtime or CDN.

The portal is the integration layer for the complete implemented Modular Brix suite. Install `modular_brix.ui` and
`modular_brix.portal` after the domain applications, then expose authentication and portal URLs:

```python
path("accounts/", include("django.contrib.auth.urls")),
path("app/", include("modular_brix.portal.urls")),
```

Users need an active membership in the selected organization. Role capabilities control read, create, and validation
access; action buttons are hidden when the matching capability is absent, and every endpoint enforces the same policy.

Theme tokens, navigation position, density, selective brick activation and external resource providers are configured
through `MODULAR_BRIX_PORTAL`. See `docs/portal_customization.md` for the integration contract and a complete example.
