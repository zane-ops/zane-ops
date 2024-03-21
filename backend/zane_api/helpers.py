from urllib.parse import urlparse

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator


def validate_url_domain(value: str):
    validate_url = URLValidator()

    try:
        validate_url('https://' + value)
        parsed = urlparse('https://' + value)
        if not parsed.netloc == value:
            raise ValidationError('Invalid domain')
    except ValidationError:
        raise ValidationError("Should be a domain without the scheme.")


def validate_url_path(value: str):
    validate_url = URLValidator()
    try:
        validate_url('https://zane.com' + value)
        parsed = urlparse('https://zane.com' + value)
        if not parsed.path == value or ".." in value:
            raise ValidationError('Invalid Path')
    except ValidationError:
        raise ValidationError("should be a valid url segment")
