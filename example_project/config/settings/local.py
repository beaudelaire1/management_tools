from .base import *  # noqa: F401,F403
from .base import BASE_DIR, postgres_database_from_env

DEBUG = True

# Development-only key: never used outside a developer machine.
SECRET_KEY = "local-development-only-key-0123456789-abcdefghijklmnopqrstuvwxyz"

ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

DATABASES = {
    "default": postgres_database_from_env()
    or {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}
