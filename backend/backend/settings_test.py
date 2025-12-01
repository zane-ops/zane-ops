# settings_test.py
from .settings import *

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
