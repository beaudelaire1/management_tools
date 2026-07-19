import os

from .base import *  # noqa: F401,F403
from .base import BASE_DIR, postgres_database_from_env

DEBUG = False

# Test-only key: deterministic, never used in a deployed environment.
SECRET_KEY = "test-only-key-0123456789-abcdefghijklmnopqrstuvwxyz-0123456789"

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]

DATABASES = {
    "default": postgres_database_from_env()
    or {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("SQLITE_TEST_DB", BASE_DIR / "db.test.sqlite3"),
    }
}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
