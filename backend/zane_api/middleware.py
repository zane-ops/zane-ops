from typing import Callable
from django.http import HttpRequest, HttpResponse
from django.conf import settings
from django.core.cache import cache
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
import requests
import socket
import time
import json
import logging
from django.utils.deprecation import MiddlewareMixin
from .formatters import ColorfulFormatter


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


class RequestLogMiddleware(MiddlewareMixin):
    """Request Logging Middleware with colorful output."""

    def __init__(self, get_response):
        super().__init__(get_response)
        self.get_response = get_response
        self.logger = logging.getLogger("request_logger")
        self.formatter = ColorfulFormatter()

    def process_request(self, request):
        # Store start time on the request
        request._start_time = time.monotonic()

        # Capture request body early for API endpoints (before it gets consumed)
        request._cached_body = None
        if "/api/" in str(request.get_full_path()):
            try:
                # Read and cache the body
                body_data = request.body
                if body_data:
                    request._cached_body = json.loads(body_data.decode("utf-8"))
                else:
                    request._cached_body = {}
            except (json.JSONDecodeError, UnicodeDecodeError):
                request._cached_body = {"error": "Could not decode request body"}
            except Exception as e:
                request._cached_body = {
                    "error": f"Error reading request body: {str(e)}"
                }

        return None

    def process_response(self, request, response):
        # Calculate duration
        start_time = getattr(request, "_start_time", time.monotonic())
        duration = (time.monotonic() - start_time) * 1000  # Convert to milliseconds

        # Prepare log data
        log_data = {
            "remote_address": request.META.get("REMOTE_ADDR", "unknown"),
            "server_hostname": socket.gethostname(),
            "request_method": request.method,
            "request_path": request.get_full_path(),
            "response_status": response.status_code,
            "run_time_ms": duration,
        }

        # Add cached request body if available
        if hasattr(request, "_cached_body") and request._cached_body is not None:
            log_data["request_body"] = request._cached_body

        # Create log record with custom data
        self.logger.info(self.formatter.format(log_data))

        return response

    def process_exception(self, request, exception):
        """Log unhandled exceptions"""
        try:
            raise exception
        except Exception as e:
            self.logger.exception(f"Unhandled Exception: {str(e)}")
        return None
