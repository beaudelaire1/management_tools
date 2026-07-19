"""Minimal integration profile proving that the portal can run with one business brick."""

from .test import *  # noqa: F401,F403

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "modular_brix.foundation.organizations",
    "modular_brix.foundation.accounts",
    "modular_brix.foundation.permissions",
    "modular_brix.ui",
    "modular_brix.management.parties",
    "modular_brix.portal",
]

MODULAR_BRIX_PORTAL = {
    "enabled_bricks": ["management_parties"],
}
