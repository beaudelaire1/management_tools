# Portal customization and brick integration

The portal is a reusable integration layer. A client project changes visual identity and layout through settings;
it does not copy core templates or edit the packaged CSS.

## Theme and layout

```python
MODULAR_BRIX_PORTAL = {
    "theme": {
        "brand": "#3156a3",
        "brand_dark": "#203b73",
        "brand_soft": "#e5ebfa",
        "accent": "#d78b2d",
        "canvas": "#f4f6fb",
        "paper": "#ffffff",
        "radius": "10px",
        "sidebar_width": "280px",
    },
    "layout": {
        "navigation": "right",  # left | right | top
        "header": "static",  # sticky | static
        "density": "compact",  # comfortable | compact
    },
    "enabled_bricks": None,
    "resource_providers": [],
}
```

Color values are restricted to six-digit hexadecimal colors. Lengths accept positive `px` and `rem` values. Invalid
tokens fail at startup or on the first portal render instead of injecting arbitrary CSS.

## Selective brick activation

`enabled_bricks` accepts Django app labels. With the following configuration, only party and sales screens are
registered in portal navigation and routes:

```python
"enabled_bricks": ["management_parties", "management_sales"],
```

`None` enables every installed brick. A resource whose model application is not installed is omitted automatically.
The reference profile `example_project.config.settings.portal_parties` is an executable proof that the portal starts
with the parties brick while commercial, finance and steering applications are absent.

## Registering a client or third-party brick

Create a provider in the client application:

```python
from modular_brix.portal.resources import Resource, field


def portal_resources():
    return (
        Resource(
            key="contracts",
            category="Gestion",
            label="Contrats",
            singular="contrat",
            model_label="client_contracts.Contract",
            organization_lookup="organization_id",
            list_fields=(field("number", "Numéro"), field("status", "Statut")),
            detail_fields=(
                field("number", "Numéro"),
                field("status", "Statut"),
                field("created_at", "Créé le"),
            ),
            search_fields=("number", "status"),
        ),
    )
```

Then register the dotted callable:

```python
"resource_providers": ["client_contracts.portal.portal_resources"],
```

The brick immediately receives the shared authenticated shell, organization isolation, navigation, search,
pagination, empty states and generic detail view. A specialized detail page can extend
`portal/resource_detail.html` and override `detail_actions` or `after_details`.

## Required structure for a complete brick

Each business brick must contain:

1. organization-bound models and migrations;
2. transactional command services and read selectors;
3. permission policies and audit events;
4. portal resources, forms and optional specialized templates;
5. unit, tenant-isolation and end-to-end tests;
6. a README describing dependencies, invariants and explicit limits.

This contract prevents a navigation entry or an HTML mock-up from being presented as an implemented tool.
