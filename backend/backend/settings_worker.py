from .settings import *

ROOT_URLCONF = "webshell.worker_urls"
ASGI_APPLICATION = "backend.worker_asgi.application"
ALLOWED_HOSTS = ["*"]
