from django.apps import AppConfig
from django.conf import settings


class ZaneApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'zane_api'

    def ready(self):
        # Only instrument the API process serving HTTP requests, never during
        # tests or in the temporal workers.
        if settings.BACKEND_COMPONENT == "API" and not settings.TESTING:
            from backend.otel import configure_opentelemetry

            configure_opentelemetry()
