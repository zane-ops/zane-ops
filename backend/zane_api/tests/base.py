from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    },
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
    CELERY_BROKER_URL="memory://",
    CELERY_TASK_STORE_EAGER_RESULT=True,
)
class APITestCase(TestCase):
    client = APIClient(enforce_csrf_checks=True, content_type="application/json")

    def tearDown(self):
        cache.clear()


class AuthAPITestCase(APITestCase):
    def setUp(self):
        User.objects.create_user(username="Fredkiss3", password="password")

    def loginUser(self):
        self.client.login(username="Fredkiss3", password="password")
        return User.objects.get(username="Fredkiss3")
