import re
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


DEFAULT_THEME = {
    "ink": "#17221f",
    "muted": "#64716d",
    "line": "#dce4e0",
    "soft": "#f3f7f5",
    "paper": "#ffffff",
    "canvas": "#edf2ef",
    "brand": "#0b6b57",
    "brand_dark": "#074c3e",
    "brand_soft": "#dff3ec",
    "accent": "#e7a935",
    "danger": "#a33b32",
    "success": "#287a55",
    "radius": "14px",
    "sidebar_width": "248px",
}

DEFAULT_LAYOUT = {
    "navigation": "left",
    "header": "sticky",
    "density": "comfortable",
}

COLOR_KEYS = {
    "ink",
    "muted",
    "line",
    "soft",
    "paper",
    "canvas",
    "brand",
    "brand_dark",
    "brand_soft",
    "accent",
    "danger",
    "success",
}
LENGTH_KEYS = {"radius", "sidebar_width"}
HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
CSS_LENGTH = re.compile(r"^(?:0|[1-9][0-9]*(?:\.[0-9]+)?(?:px|rem))$")


@dataclass(frozen=True)
class PortalConfiguration:
    theme: dict[str, str]
    navigation: str
    header: str
    density: str
    enabled_bricks: tuple[str, ...] | None
    resource_providers: tuple[str, ...]

    @property
    def css_variables(self) -> tuple[tuple[str, str], ...]:
        return tuple((key.replace("_", "-"), value) for key, value in self.theme.items())

    @property
    def body_classes(self) -> str:
        return f"layout-nav-{self.navigation} header-{self.header} density-{self.density}"


def _mapping(value: object, *, setting_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ImproperlyConfigured(f"{setting_name} must be a dictionary.")
    return value


def _validate_theme(overrides: dict[str, Any]) -> dict[str, str]:
    unknown = set(overrides) - set(DEFAULT_THEME)
    if unknown:
        raise ImproperlyConfigured(f"Unknown portal theme tokens: {', '.join(sorted(unknown))}.")
    theme = {**DEFAULT_THEME, **overrides}
    for key, value in theme.items():
        if not isinstance(value, str):
            raise ImproperlyConfigured(f"Portal theme token '{key}' must be a string.")
        if key in COLOR_KEYS and not HEX_COLOR.fullmatch(value):
            raise ImproperlyConfigured(f"Portal theme token '{key}' must be a six-digit hexadecimal color.")
        if key in LENGTH_KEYS and not CSS_LENGTH.fullmatch(value):
            raise ImproperlyConfigured(f"Portal theme token '{key}' must be a px or rem length.")
    return theme


def _choice(value: object, *, setting_name: str, choices: set[str]) -> str:
    if not isinstance(value, str) or value not in choices:
        allowed = ", ".join(sorted(choices))
        raise ImproperlyConfigured(f"{setting_name} must be one of: {allowed}.")
    return value


def _string_tuple(value: object, *, setting_name: str, allow_none: bool = False) -> tuple[str, ...] | None:
    if value is None and allow_none:
        return None
    if not isinstance(value, (list, tuple)) or any(not isinstance(item, str) for item in value):
        raise ImproperlyConfigured(f"{setting_name} must be a list of strings.")
    return tuple(value)


def load_portal_configuration() -> PortalConfiguration:
    raw = _mapping(getattr(settings, "MODULAR_BRIX_PORTAL", {}), setting_name="MODULAR_BRIX_PORTAL")
    layout = {**DEFAULT_LAYOUT, **_mapping(raw.get("layout"), setting_name="MODULAR_BRIX_PORTAL['layout']")}
    unknown_layout = set(layout) - set(DEFAULT_LAYOUT)
    if unknown_layout:
        raise ImproperlyConfigured(f"Unknown portal layout options: {', '.join(sorted(unknown_layout))}.")
    return PortalConfiguration(
        theme=_validate_theme(_mapping(raw.get("theme"), setting_name="MODULAR_BRIX_PORTAL['theme']")),
        navigation=_choice(
            layout["navigation"],
            setting_name="MODULAR_BRIX_PORTAL['layout']['navigation']",
            choices={"left", "right", "top"},
        ),
        header=_choice(
            layout["header"],
            setting_name="MODULAR_BRIX_PORTAL['layout']['header']",
            choices={"sticky", "static"},
        ),
        density=_choice(
            layout["density"],
            setting_name="MODULAR_BRIX_PORTAL['layout']['density']",
            choices={"comfortable", "compact"},
        ),
        enabled_bricks=_string_tuple(
            raw.get("enabled_bricks"),
            setting_name="MODULAR_BRIX_PORTAL['enabled_bricks']",
            allow_none=True,
        ),
        resource_providers=_string_tuple(
            raw.get("resource_providers", []),
            setting_name="MODULAR_BRIX_PORTAL['resource_providers']",
        ) or (),
    )
