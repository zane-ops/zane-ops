from drf_standardized_errors.handler import ExceptionHandler
from rest_framework import exceptions, status


class CustomThrottledException(exceptions.Throttled):
    default_detail = "You made too Many requests in a short amount of time,"
    extra_detail_plural = "Please wait for {wait} seconds before retrying your action."
    extra_detail_singular = (
        "Please wait for {wait} seconds before retrying your action."
    )


class ResourceConflict(exceptions.APIException):
    status_code = 409
    default_detail = (
        "The action you tried to perform is not possible because"
        " another resource already exists with the same ID."
    )
    default_code = "resource_conflict"


class CustomExceptionHandler(ExceptionHandler):
    def convert_known_exceptions(self, exc: Exception) -> Exception:
        if isinstance(exc, exceptions.Throttled):
            return CustomThrottledException(wait=exc.wait)
        if isinstance(exc, exceptions.AuthenticationFailed):
            exc.status_code = status.HTTP_401_UNAUTHORIZED
        if (
            isinstance(exc, exceptions.NotAuthenticated)
            and exc.detail == exc.default_detail
        ):
            exc = exceptions.NotAuthenticated(
                detail="Authentication required. Please log in to access this resource.",
            )
        return super().convert_known_exceptions(exc)
