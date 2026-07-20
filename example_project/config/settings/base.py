import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[3]

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
DEBUG = False
ALLOWED_HOSTS: list[str] = []

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
    "modular_brix.foundation.audit",
    "modular_brix.foundation.workflows",
    "modular_brix.foundation.documents",
    "modular_brix.foundation.notifications",
    "modular_brix.foundation.configuration",
    "modular_brix.foundation.sequences",
    "modular_brix.foundation.reference_data",
    "modular_brix.foundation.data_transfer",
    "modular_brix.ui",
    "modular_brix.management.parties",
    "modular_brix.management.crm",
    "modular_brix.management.catalog",
    "modular_brix.management.sales",
    "modular_brix.management.purchasing",
    "modular_brix.management.stock",
    "modular_brix.management.projects",
    "modular_brix.management.interventions",
    "modular_brix.management.scheduling",
    "modular_brix.management.time_tracking",
    "modular_brix.management.contracts",
    "modular_brix.management.support",
    "modular_brix.management.assets",
    "modular_brix.management.workforce",
    "modular_brix.finance.billing",
    "modular_brix.finance.payments",
    "modular_brix.finance.receivables",
    "modular_brix.finance.expenses",
    "modular_brix.finance.payables",
    "modular_brix.finance.banking",
    "modular_brix.finance.preaccounting",
    "modular_brix.finance.ledger",
    "modular_brix.finance.subledger",
    "modular_brix.finance.analytic",
    "modular_brix.finance.tax",
    "modular_brix.finance.fixed_assets",
    "modular_brix.finance.closing",
    "modular_brix.finance.einvoicing",
    "modular_brix.finance.exports",
    "modular_brix.steering.indicators",
    "modular_brix.steering.dashboards",
    "modular_brix.steering.objectives",
    "modular_brix.steering.budgeting",
    "modular_brix.steering.forecasts",
    "modular_brix.steering.cashflow",
    "modular_brix.steering.analytics",
    "modular_brix.steering.reports",
    "modular_brix.steering.capacity",
    "modular_brix.steering.risks",
    "modular_brix.steering.quality",
    "modular_brix.portal",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "example_project.config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "example_project" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

WSGI_APPLICATION = "example_project.config.wsgi.application"
ASGI_APPLICATION = "example_project.config.asgi.application"


def postgres_database_from_env() -> dict | None:
    if not os.environ.get("POSTGRES_DB"):
        return None
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ["POSTGRES_DB"],
        "USER": os.environ.get("POSTGRES_USER", "postgres"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }


AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"

# Client projects may override these tokens without copying templates or CSS.
MODULAR_BRIX_PORTAL = {
    "theme": {
        "brand": "#0b6b57",
        "brand_dark": "#074c3e",
        "brand_soft": "#dff3ec",
        "accent": "#e7a935",
    },
    "layout": {
        "navigation": "left",  # left | right | top
        "header": "sticky",  # sticky | static
        "density": "comfortable",  # comfortable | compact
    },
    "enabled_bricks": None,  # None enables every installed brick.
    "resource_providers": [],  # Dotted callables returning additional portal Resource objects.
}

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "portal:organization-picker"
LOGOUT_REDIRECT_URL = "login"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
