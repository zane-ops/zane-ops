"""
ASGI config for backend project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/howto/deployment/asgi/
"""

import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from channels.security.websocket import AllowedHostsOriginValidator

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
# Initialize Django ASGI application early to ensure the AppRegistry
# is populated before importing code that may import ORM models.
asgi_application = get_asgi_application()

from webshell.routing import websocket_urlpatterns


application = ProtocolTypeRouter(
    {
        "http": asgi_application,
        "websocket":
        # AllowedHostsOriginValidator(
        #     AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns),
        # )
        # ),
    }
)
