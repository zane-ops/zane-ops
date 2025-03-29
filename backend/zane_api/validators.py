import re
from urllib.parse import urlparse

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator


def validate_url_domain(value: str):
    validate_url = URLValidator()
    wildcard = "*."
    try:
        if value.startswith(wildcard):
            prefix, domain = value.split(wildcard)
            if len(prefix) != 0:
                raise ValidationError("Invalid domain")
            value = domain

        validate_url("https://" + value)
        parsed = urlparse("https://" + value)
        if not parsed.netloc == value:
            raise ValidationError("Invalid domain")
    except ValidationError:
        raise ValidationError("Should be a domain without the scheme or pathname.")
    except Exception:
        raise ValidationError("Invalid domain")


def validate_url_path(value: str):
    validate_url = URLValidator()
    try:
        validate_url("https://zane.com" + value)
        parsed = urlparse("https://zane.com" + value)
        if not parsed.path == value or ".." in value or "*" in value:
            raise ValidationError("Invalid Path")
    except ValidationError:
        raise ValidationError(
            "should be a valid pathname starting with `/` and not containing query parameters, `..` or `*`"
        )


def validate_env_name(value: str):
    pattern = r"^[A-Za-z_][A-Za-z0-9_]*$"
    if not bool(re.match(pattern, value)):
        raise ValidationError(
            "shoud starts with an underscore (_) or a letter followed by letters, number or underscores(_)"
        )


def validate_git_commit_sha(value):
    commit_sha_regex = re.compile(r"^(HEAD|[0-9a-f]{7,40})$", re.IGNORECASE)
    if not commit_sha_regex.fullmatch(value):
        raise ValidationError(f"'{value}' is not a valid Git commit SHA or 'HEAD'.")
