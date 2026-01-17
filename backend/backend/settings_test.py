# settings_test.py
from .settings import *
from datetime import timedelta

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "zane",
        "USER": "postgres",
        "PASSWORD": "password",
        "HOST": "localhost",
        "PORT": "5434",
        # Performance optimizations for tests
        "OPTIONS": {
            "connect_timeout": 10,
        },
        "TEST": {
            "TEMPLATE": "template0",
        },
    }
}


TESTING = True

CADDY_PROXY_ADMIN_HOST = "http://127.0.0.1:2020"
TEMPORALIO_WORKFLOW_EXECUTION_MAX_TIMEOUT = timedelta(seconds=7)
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["anon"] = "5/minute"


# Disable migrations for faster test database setup
class DisableMigrations:
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None


MIGRATION_MODULES = DisableMigrations()

# Faster password hashing in tests
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

SQL_DEBUG = os.environ.get("SQL_DEBUG", "false") == "true"

if SQL_DEBUG:
    LOGGING["loggers"]["django.db.backends"] = {
        "handlers": ["console"],
        "level": "DEBUG",
        "propagate": True,
    }
