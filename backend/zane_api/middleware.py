from typing import Callable
from django.http import HttpRequest, HttpResponse
from django.conf import settings
from django.core.cache import cache
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
import requests


class AddCommitShaHeadersMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        response = self.get_response(request)
        if settings.COMMIT_SHA is not None:
            response["X-Commit-Sha"] = settings.COMMIT_SHA
        return response


class TelemetryMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        if (
            not settings.DEBUG
            and not settings.TESTING
            and not isinstance(request.user, AnonymousUser)
            and settings.TELEMETRY_ENABLED
        ):
            last_ping = cache.get("zane:last_ping")
            if last_ping is None:
                last_ping = timezone.now()
                # ping at most every 30 minutes
                cache.set("zane:last_ping", last_ping, 30 * 60)

                # send `PING`
                try:
                    requests.post("https://cdn.zaneops.dev/api/ping")
                except Exception:
                    # we don't want to break the app if the CDN is not accessible from within this node
                    pass
        return self.get_response(request)
