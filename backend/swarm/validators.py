import re
from django.core.exceptions import ValidationError


def validate_unix_username(value):
    username_regex = re.compile(r"^[a-z][-a-z0-9_]*$")
    if not username_regex.fullmatch(value):
        raise ValidationError(f"'{value}' is not a valid unix username.")
