from collections import OrderedDict
from typing import Any

from drf_standardized_errors.handler import ExceptionHandler
from rest_framework import exceptions, status

EMPTY_RESPONSE = {}
EMPTY_PAGINATED_RESPONSE = OrderedDict(
    [("count", 0), ("next", None), ("previous", None), ("results", [])]
)
EMPTY_CURSOR_RESPONSE = OrderedDict(
    [("next", None), ("previous", None), ("results", [])]
)


class ThrottledExceptionWithWaitTime(exceptions.Throttled):
    default_detail = "You made too Many requests in a short amount of time,"
    extra_detail_singular = (
        "Please wait for {wait} seconds before retrying your action."
    )
    extra_detail_plural = extra_detail_singular


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
            return ThrottledExceptionWithWaitTime(wait=exc.wait)
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


def drf_spectular_mark_all_outputs_required(result: Any, **kwargs: Any):
    """
    Mark all response outputs as required in the openAPI specification,
    because DRF spectucular was mistakenly making non read only fields as optional
    solution copied from : https://github.com/tfranzel/drf-spectacular/issues/480#issuecomment-898488288
    """
    schemas = result.get("components", {}).get("schemas", {})
    for name, schema in schemas.items():  # type: str, Any
        if "properties" not in schema:
            continue
        # Add required fields in the api where the api lacks to add it
        if name.endswith("FieldChangeRequest") or name.endswith("ItemChangeRequest"):
            if "required" in schema:
                if "field" not in schema["required"]:
                    schema["required"] += ["field"]
            else:
                schema["required"] = ["field"]
            if name.endswith("FieldChangeRequest"):
                if "new_value" not in schema["required"]:
                    schema["required"] += ["new_value"]
        if name.endswith("Request"):
            continue
        schema["required"] = sorted(schema["properties"].keys())
    return result
