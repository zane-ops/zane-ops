"""
Django settings for backend project.

Generated by 'django-admin startproject' using Django 5.0.2.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/5.0/ref/settings/
"""

import asyncio
import os
import sys
from datetime import timedelta
from pathlib import Path

import uvloop
from dotenv_vault import load_dotenv

from .api_description import API_DESCRIPTION
from .bootstrap import register_zaneops_app_on_proxy

loop = uvloop.new_event_loop()
asyncio.set_event_loop(loop)

try:
    load_dotenv(".env", override=True)
except FileNotFoundError:
    pass

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-^@$8fc&u2j)4@k+p+bg0ei8sm+@+pwq)hstk$a*0*7#k54kybx",
)

TESTING = len(sys.argv) > 1 and sys.argv[1] == "test"
ENVIRONMENT = os.environ.get("ENVIRONMENT", "DEVELOPMENT")
PRODUCTION_ENV = "PRODUCTION"
BACKEND_COMPONENT = os.environ.get("BACKEND_COMPONENT", "API")
__DANGEROUS_ALLOW_HTTP_SESSION = (
    os.environ.get("__DANGEROUS_ALLOW_HTTP_SESSION") == "true"
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = ENVIRONMENT != PRODUCTION_ENV
CSRF_COOKIE_SECURE = (
    False if __DANGEROUS_ALLOW_HTTP_SESSION else ENVIRONMENT == PRODUCTION_ENV
)
SESSION_COOKIE_SECURE = (
    False if __DANGEROUS_ALLOW_HTTP_SESSION else ENVIRONMENT == PRODUCTION_ENV
)
REDIS_URL = os.environ.get("REDIS_URL", "redis://127.0.0.1:6381/0")
SECURE_HSTS_SECONDS = (
    0 if (__DANGEROUS_ALLOW_HTTP_SESSION or ENVIRONMENT != PRODUCTION_ENV) else 60
)

# We will only support one root domain on production
# And it will be in the format domain.com (without `http://` or `https://`)
ROOT_DOMAIN = os.environ.get("ROOT_DOMAIN", "127-0-0-1.sslip.io")
ZANE_APP_DOMAIN = os.environ.get("ZANE_APP_DOMAIN", "127-0-0-1.sslip.io")
ZANE_INTERNAL_DOMAIN = "zaneops.internal"

ALLOWED_HOSTS = (
    [
        f".{ROOT_DOMAIN}",
        "localhost",
        "127.0.0.1",
        ZANE_APP_DOMAIN,
        "host.docker.internal",
    ]
    if ENVIRONMENT != PRODUCTION_ENV
    else [f".{ROOT_DOMAIN}", f"zane.api.zaneops.internal"]
)

SESSION_COOKIE_DOMAIN = None

if ENVIRONMENT == PRODUCTION_ENV:
    is_same_subdomain = ZANE_APP_DOMAIN.endswith(ROOT_DOMAIN)
    if is_same_subdomain:
        SESSION_COOKIE_DOMAIN = f".{ROOT_DOMAIN}"
    else:
        SESSION_COOKIE_DOMAIN = ZANE_APP_DOMAIN

# This is necessary for making sure that CSRF protections work on production
CSRF_TRUSTED_ORIGINS = (
    [f"https://{ZANE_APP_DOMAIN}", f"http://{ZANE_APP_DOMAIN}", "http://localhost:5678"]
    if ENVIRONMENT != PRODUCTION_ENV
    else [f"https://{ZANE_APP_DOMAIN}"]
)
CORS_ALLOW_ALL_ORIGINS = ENVIRONMENT != PRODUCTION_ENV
if ENVIRONMENT == PRODUCTION_ENV:
    CORS_ALLOWED_ORIGINS = CSRF_TRUSTED_ORIGINS

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}

SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_EXPIRE_THRESHOLD = 2
SESSION_EXTEND_PERIOD = 7
# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "zane_api.apps.ZaneApiConfig",
    "corsheaders",
    "rest_framework",
    "rest_framework.authtoken",
    "drf_spectacular",
    "django_celery_results",
    "django_celery_beat",
    "drf_standardized_errors",
    "django_filters",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "backend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "backend.wsgi.application"
ASGI_APPLICATION = "backend.asgi.application"

# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "zane"),
        "USER": os.environ.get("DB_USER", "postgres"),
        "PASSWORD": os.environ.get("DB_PASSWORD", "password"),
        "HOST": os.environ.get("DB_HOST", "127.0.0.1"),
        "PORT": os.environ.get("DB_PORT", "5434"),
    }
}

# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Internationalization
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

STATIC_URL = "static/"

# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# DB Logging for queries

LOGGING = {
    "version": 1,
    "filters": {
        "require_debug_true": {
            "()": "django.utils.log.RequireDebugTrue",
        }
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "filters": ["require_debug_true"],
            "class": "logging.StreamHandler",
        }
    },
    "loggers": {
        "gunicorn.error": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": True,
        },
        "gunicorn.access": {
            "level": "DEBUG",
            "handlers": ["console"],
            "propagate": True,
        },
    },
}


if DEBUG and not os.environ.get("SILENT"):
    LOGGING["loggers"].update(
        {
            "django.db.backends": {
                "level": "DEBUG",
                "handlers": ["console"],
            },
        }
    )


# Django Rest framework

REST_FRAMEWORK_DEFAULT_RENDERER_CLASSES = ("rest_framework.renderers.JSONRenderer",)

if DEBUG:
    REST_FRAMEWORK_DEFAULT_RENDERER_CLASSES = (
        REST_FRAMEWORK_DEFAULT_RENDERER_CLASSES
        + ("rest_framework.renderers.BrowsableAPIRenderer",)
    )

REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "5/minute",
        "tls_certificates": "60/minute",
        "log_collect": "30/minute",
    },
    "DEFAULT_RENDERER_CLASSES": REST_FRAMEWORK_DEFAULT_RENDERER_CLASSES,
    "EXCEPTION_HANDLER": "drf_standardized_errors.handler.exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_standardized_errors.openapi.AutoSchema",
}

DRF_STANDARDIZED_ERRORS = {
    "EXCEPTION_HANDLER_CLASS": "zane_api.views.CustomExceptionHandler",
    "ALLOWED_ERROR_STATUS_CODES": [
        "400",
        "401",
        "403",
        "404",
        "429",
    ],
}

# DRF SPECTACULAR, for OpenAPI schema generation


SPECTACULAR_SETTINGS = {
    "TITLE": "ZaneOps API",
    "DESCRIPTION": API_DESCRIPTION,
    "VERSION": "0.0.1-alpha",
    "SERVE_INCLUDE_SCHEMA": False,
    "SERVERS": [{"url": "https://lab.fkiss.me/"}],
    "ENUM_NAME_OVERRIDES": {
        "ValidationErrorEnum": "drf_standardized_errors.openapi_serializers.ValidationErrorEnum.choices",
        "ClientErrorEnum": "drf_standardized_errors.openapi_serializers.ClientErrorEnum.choices",
        "ServerErrorEnum": "drf_standardized_errors.openapi_serializers.ServerErrorEnum.choices",
        "ErrorCode401Enum": "drf_standardized_errors.openapi_serializers.ErrorCode401Enum.choices",
        "ErrorCode403Enum": "drf_standardized_errors.openapi_serializers.ErrorCode403Enum.choices",
        "ErrorCode404Enum": "drf_standardized_errors.openapi_serializers.ErrorCode404Enum.choices",
        "ErrorCode405Enum": "drf_standardized_errors.openapi_serializers.ErrorCode405Enum.choices",
        "ErrorCode406Enum": "drf_standardized_errors.openapi_serializers.ErrorCode406Enum.choices",
        "ErrorCode415Enum": "drf_standardized_errors.openapi_serializers.ErrorCode415Enum.choices",
        "ErrorCode429Enum": "drf_standardized_errors.openapi_serializers.ErrorCode429Enum.choices",
        "ErrorCode500Enum": "drf_standardized_errors.openapi_serializers.ErrorCode500Enum.choices",
        "ItemChangeTypeEnum": (
            ("ADD", "Add"),
            ("DELETE", "Delete"),
            ("UPDATE", "Update"),
        ),
        "FieldChangeTypeEnum": (("UPDATE", "Update"),),
        "ServiceStatusEnum": (
            ("HEALTHY", "Healthy"),
            ("UNHEALTHY", "Unhealthy"),
            ("SLEEPING", "Sleeping"),
            ("NOT_DEPLOYED_YET", "Not deployed yet"),
            ("DEPLOYING", "Deploying"),
        ),
    },
    "POSTPROCESSING_HOOKS": [
        "drf_standardized_errors.openapi_hooks.postprocess_schema_enums",
        "zane_api.views.drf_spectular_mark_all_outputs_required",
    ],
    "COMPONENT_SPLIT_REQUEST": True,
    "ENFORCE_NON_BLANK_FIELDS": True,
}

# For having colorized output in tests
TEST_RUNNER = "redgreenunittest.django.runner.RedGreenDiscoverRunner"

# Zane proxy config
CADDY_PROXY_ADMIN_HOST = os.environ.get(
    "CADDY_PROXY_ADMIN_HOST",
    "http://127.0.0.1:2020" if TESTING else "http://127.0.0.1:2019",
)
ZANE_API_SERVICE_INTERNAL_DOMAIN = (
    "host.docker.internal:8000"
    if ENVIRONMENT != PRODUCTION_ENV
    else f"zane.api.zaneops.internal:8000"
)
ZANE_FRONT_SERVICE_INTERNAL_DOMAIN = (
    "host.docker.internal:5678"
    if ENVIRONMENT != PRODUCTION_ENV
    else f"zane.front.zaneops.internal:80"
)
ZANE_FLUENTD_HOST = os.environ.get(
    "ZANE_FLUENTD_HOST", "unix://$HOME/.fluentd/fluentd.sock"
)

DEFAULT_HEALTHCHECK_TIMEOUT = 30  # seconds
DEFAULT_HEALTHCHECK_INTERVAL = 30  # seconds
DEFAULT_HEALTHCHECK_WAIT_INTERVAL = 5.0  # seconds

# temporalio config
TEMPORALIO_WORKFLOW_EXECUTION_MAX_TIMEOUT = timedelta(minutes=30)
TEMPORALIO_SERVER_URL = os.environ.get("TEMPORALIO_SERVER_URL", "127.0.0.1:7233")
TEMPORALIO_MAIN_TASK_QUEUE = "main-task-queue"
TEMPORALIO_SCHEDULE_TASK_QUEUE = "schedule-task-queue"
TEMPORALIO_WORKER_TASK_QUEUE = os.environ.get(
    "TEMPORALIO_WORKER_TASK_QUEUE", TEMPORALIO_MAIN_TASK_QUEUE
)
TEMPORALIO_WORKER_NAMESPACE = "zane"

if BACKEND_COMPONENT == "API":
    register_zaneops_app_on_proxy(
        proxy_url=CADDY_PROXY_ADMIN_HOST,
        zane_app_domain=ZANE_APP_DOMAIN,
        zane_api_internal_domain=ZANE_API_SERVICE_INTERNAL_DOMAIN,
        zane_front_internal_domain=ZANE_FRONT_SERVICE_INTERNAL_DOMAIN,
        internal_tls=DEBUG,
    )
