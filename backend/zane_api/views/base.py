from typing import Any

from drf_standardized_errors.handler import exception_handler
from rest_framework import status
from rest_framework.exceptions import NotAuthenticated, PermissionDenied, Throttled
from rest_framework.response import Response


class CustomThrottledException(Throttled):
    extra_detail_plural = ""
    extra_detail_singular = ""


def custom_exception_handler(exception: Any, context: Any) -> Response:
    if isinstance(exception, Throttled):
        exception = CustomThrottledException(
            wait=exception.wait,
            detail="You made too Many requests in a short amount of time, "
            f"Please wait for {exception.wait} seconds before retrying your action.",
        )
    if isinstance(exception, NotAuthenticated):
        exception.detail = NotAuthenticated(
            detail="Authentication required. Please log in to access this resource.",
            code=exception.default_code,
        )
    if isinstance(exception, PermissionDenied):
        exception.status_code = status.HTTP_401_UNAUTHORIZED
    return exception_handler(exception, context)
