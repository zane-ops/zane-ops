import re
import logging
from urllib.parse import urlparse

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator

# Get the logger for this module
logger = logging.getLogger(__name__)


def validate_url_domain(value: str) -> None:
    """
    Validates if the given value is a valid URL domain.

    Args:
        value: The string to validate.

    Raises:
        ValidationError: If the value is not a valid URL domain.
    """
    validate_url = URLValidator()
    wildcard = "*."
    try:
        if value.startswith(wildcard):
            prefix, domain = value.split(wildcard, 1)  # Split only once
            if prefix:  # Check if prefix is not empty
                raise ValidationError("Invalid domain: Wildcard prefix is invalid.")
            value = domain

        # Add a scheme for validation but it is not important
        validate_url("https://" + value)
        parsed = urlparse("https://" + value)

        # Check if the netloc (network location) matches the value
        if parsed.netloc != value:
            raise ValidationError(
                "Invalid domain: The domain does not match the parsed netloc."
            )

    except ValidationError as e:
        logger.debug(f"Validation error for URL domain: {e}")
        raise ValidationError(
            "Should be a domain without the scheme or pathname and must be valid."
        ) from e
    except Exception as e:
        logger.exception(f"Unexpected error during URL domain validation: {e}")
        raise ValidationError(f"Invalid domain: An unexpected error occurred.") from e


def validate_url_path(value: str) -> None:
    """
    Validates if the given value is a valid URL path.

    Args:
        value: The string to validate.

    Raises:
        ValidationError: If the value is not a valid URL path.
    """
    validate_url = URLValidator()
    try:
        # Append the value to a base URL for validation
        validate_url("https://zane.com" + value)
        parsed = urlparse("https://zane.com" + value)

        # Check if path matches and ensure no ".." or "*" present
        if not parsed.path == value or ".." in value or "*" in value:
            raise ValidationError(
                "Invalid path: Path does not match or contains invalid characters."
            )

    except ValidationError as e:
        logger.debug(f"Validation error for URL path: {e}")
        raise ValidationError(
            "Should be a valid pathname starting with `/` and not containing query parameters, `..` or `*`."
        ) from e
    except Exception as e:
        logger.exception(f"Unexpected error during URL path validation: {e}")
        raise ValidationError("Invalid path: An unexpected error occurred.") from e


def validate_env_name(value: str) -> None:
    """
    Validates if the given value is a valid environment variable name.

    Args:
        value: The string to validate.

    Raises:
        ValidationError: If the value is not a valid environment variable name.
    """
    pattern = r"^[A-Za-z_][A-Za-z0-9_]*$"
    if not re.match(pattern, value):
        raise ValidationError(
            "Should start with an underscore (_) or a letter followed by letters, numbers, or underscores(_)."
        )
