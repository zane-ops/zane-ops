import dataclasses
import datetime
import hashlib
import json
import random
import shlex
import string
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import Any, Callable, Sequence, Optional, Literal
import re
from django.core.cache import cache
from datetime import timedelta


def cache_result(timeout: timedelta | None = None, cache_key: str | None = None):
    def decorator(func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            # Generate a cache key if not provided
            key = (
                cache_key
                or f"{func.__name__}_{'_'.join(map(str, args))}_{'_'.join(f'{k}_{v}' for k, v in kwargs.items())}".replace(
                    " ", "_"
                )
            )

            # Try to get the result from the cache
            result = cache.get(key)
            ttl_seconds = None if timeout is None else int(timeout.total_seconds())
            if result is None:
                # If cache miss, call the function and cache the result
                result = func(*args, **kwargs)
                cache.set(key, result, ttl_seconds)
            return result

        return wrapped

    return decorator


def strip_slash_if_exists(
    string: str,
    strip_end: bool = False,
    strip_start: bool = True,
):
    final_str = string
    if strip_start:
        final_str = final_str.lstrip("/")
    if strip_end:
        final_str = final_str.rstrip("/")
    return final_str


def add_suffix_if_missing(string: str, suffix: str):
    final_str = string
    if not string.endswith(suffix):
        final_str = final_str + suffix
    return final_str


def datetime_to_timestamp_string(_date: datetime.datetime):
    return str(_date.timestamp()).replace(".", "")


class DockerSwarmTaskState(Enum):
    NEW = "new"
    PENDING = "pending"
    ASSIGNED = "assigned"
    ACCEPTED = "accepted"
    READY = "ready"
    PREPARING = "preparing"
    STARTING = "starting"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    SHUTDOWN = "shutdown"
    REJECTED = "rejected"
    ORPHANED = "orphaned"
    REMOVE = "remove"


@dataclass
class Version:
    Index: int


@dataclass
class ContainerStatus:
    ExitCode: int
    ContainerID: str | None


@dataclass
class Status:
    Timestamp: str
    State: DockerSwarmTaskState
    Message: str
    Err: str | None
    ContainerStatus: ContainerStatus | None


@dataclass
class DockerSwarmTask:
    ID: str
    Version: Version
    CreatedAt: str
    UpdatedAt: str
    Status: Status
    DesiredState: DockerSwarmTaskState

    @property
    def container_id(self):
        container_status = self.Status.ContainerStatus
        return container_status.ContainerID if container_status is not None else None

    @property
    def state(self):
        return self.Status.State

    @classmethod
    def from_dict(
        cls,
        data: dict[str, str | int | dict[str, str | int | dict]],
    ) -> "DockerSwarmTask":
        version = Version(**data["Version"])  # type: ignore
        status_data = data["Status"]
        container_status: None | ContainerStatus = None
        container_status_data = data["Status"].get("ContainerStatus")  # type: ignore
        if container_status_data is not None:
            container_status = ContainerStatus(
                ExitCode=container_status_data["ExitCode"],  # type: ignore
                ContainerID=container_status_data.get("ContainerID"),  # type: ignore
            )

        task_status = Status(
            Timestamp=status_data["Timestamp"],  # type: ignore
            State=DockerSwarmTaskState(status_data["State"]),  # type: ignore
            Message=status_data["Message"],  # type: ignore
            ContainerStatus=container_status,
            Err=status_data.get("Err"),  # type: ignore
        )
        return DockerSwarmTask(
            ID=data["ID"],  # type: ignore
            Version=version,
            CreatedAt=data["CreatedAt"],  # type: ignore
            UpdatedAt=data["UpdatedAt"],  # type: ignore
            Status=task_status,
            DesiredState=DockerSwarmTaskState(data["DesiredState"]),
        )


class LockAcquisitionError(Exception):
    """Exception raised when a lock cannot be acquired."""

    def __init__(self, message: str, countdown: int):
        super().__init__(message)
        self.countdown = countdown


def format_duration(seconds: float):
    seconds = round(seconds)  # Round to nearest integer
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    remaining_seconds = seconds % 60

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if remaining_seconds > 0 or not parts:  # always show seconds if nothing else
        parts.append(f"{remaining_seconds}s")

    return " ".join(parts)


def convert_value_to_bytes(
    value: float,
    unit: Literal["BYTES", "KILOBYTES", "MEGABYTES", "GIGABYTES"] = "BYTES",
):
    match unit:
        case "BYTES":
            return int(value)
        case "KILOBYTES":
            return int(value * 1024)
        case "MEGABYTES":
            return int(value * 1024 * 1024)
        case "GIGABYTES":
            return int(value * 1024 * 1024 * 1024)
        case _:
            raise ValueError(
                f"Unit `{unit}` is not valid, must be one of `BYTES`, `KILOBYTES`, `MEGABYTES` or `GIGABYTES`",
            )


def format_storage_value(value: int):
    kb = 1024
    mb = 1024 * kb
    gb = 1024 * mb

    if value < kb:
        return f"{value} bytes"
    if value < mb:
        return f"{value/kb:.2f} kb"
    if value < gb:
        return f"{value/mb:.2f} mb"
    return f"{value/gb:.2f} gb"


def jprint(value: Any):
    """
    Print & format value as JSON
    """
    return print(json.dumps(value, indent=2, cls=EnhancedJSONEncoder))


def find_item_in_sequence[T](
    predicate: Callable[[T], bool], sequence: Sequence[T]
) -> Optional[T]:
    return next(
        (item for item in sequence if predicate(item)),
        None,
    )


class EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)  # type: ignore
        return super().default(o)


def random_word(length: int = 10):
    letters = string.ascii_lowercase
    return "".join(random.choice(letters) for _ in range(length))


def generate_random_chars(length: int):
    """
    Generate a random set of characters comprised of letters & digits
    """
    letters = string.ascii_letters + string.digits
    return "".join(random.choice(letters) for _ in range(length))


class Colors:
    GREEN = "\033[92m"
    BLUE = "\033[94m"
    ORANGE = "\033[38;5;208m"
    YELLOW = "\033[33m"
    RED = "\033[91m"
    GREY = "\033[90m"
    ENDC = "\033[0m"  # Reset to default color


def escape_ansi(content: str):
    ANSI_ESCAPE_PATTERN = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ANSI_ESCAPE_PATTERN.sub("", content)


def excerpt(text: str, max_length: int):
    if len(text) <= max_length:
        return text
    return text[: max_length - 3].rstrip() + "..."


def truncate_utf8(utf8_string: str, limit: int) -> list[str]:
    """
    Splits a UTF-8 string into chunks of specified byte size limit while preserving UTF-8 character boundaries.

    This function takes a string and splits it into multiple parts, ensuring that each part's UTF-8 encoded
    byte length does not exceed the specified limit and that no UTF-8 characters are split across chunks.

    Args:
        s (str): The input string to be truncated/split
        limit (int): Maximum number of bytes allowed in each chunk

    Returns:
        list[str]: A list of string chunks, where each chunk's UTF-8 encoded form is within the byte limit

    Example:
        >>> text = "Hello 🌍 World!"
        >>> truncate_utf8(text, 10)
        ['Hello 🌍', ' World!']

    Note:
        - The function preserves UTF-8 character boundaries to prevent corruption
        - Uses 'ignore' error handling for decoding to handle any potential invalid UTF-8 sequences
    """
    result = []
    remaining = utf8_string

    while remaining:
        # Encode the current remaining string into bytes
        encoded = remaining.encode("utf-8")

        # If the byte length is within the limit, add the remaining part and break
        if len(encoded) <= limit:
            result.append(remaining)
            break

        # Find the last valid byte position within the limit
        valid_end = limit
        """
        https://stackoverflow.com/a/59451718/10322846
        In UTF-8, continuation bytes always start with the bit pattern `10xxxxxx`. we check for the continuation byte by:
        1. Using the mask `11000000` to clear all bits except the first two.
        2. Checking if those two bits match `10000000`.

        example:
            # Example continuation byte: 10101010
            # Mask:                      11000000
            # After & operation:         10000000  ✓ Matches what we want
        """
        while valid_end > 0 and (encoded[valid_end] & 0b11000000) == 0b10000000:
            valid_end -= 1

        # Decode the valid part and update the remaining part
        truncated = encoded[:valid_end].decode("utf-8", errors="ignore")
        remaining = encoded[valid_end:].decode("utf-8", errors="ignore")

        result.append(truncated)

    return result


def iso_to_ns(iso_string: str) -> int:
    """
    Convert an ISO datetime string with nanosecond precision to a timestamp in nanoseconds.

    Parameters:
        iso_string (str): ISO datetime string with nanoseconds, e.g. "2025-03-04T17:37:00.033944066+0000"

    Returns:
        int: Timestamp in nanoseconds since the Unix epoch.

    Raises:
        ValueError: If the input string is not in the expected ISO datetime format.
    """
    # Split into datetime part, fractional seconds, and timezone offset
    match = re.match(r"(.*?)(\.\d+)?([+-]\d{4})$", iso_string)
    if not match:
        return int(datetime.datetime.fromisoformat(iso_string).timestamp() * 1e9)

    main_part, frac, tz_str = match.group(1), match.group(2), match.group(3)
    frac = frac if frac else ".0"

    # Parse datetime ignoring fractional seconds
    dt = datetime.datetime.strptime(main_part + tz_str, "%Y-%m-%dT%H:%M:%S%z")

    # Ensure fractional seconds have exactly 9 digits (nanosecond precision)
    frac_digits = frac[1:].ljust(9, "0")[:9]
    nano_frac = int(frac_digits)

    # Calculate total nanoseconds since Unix epoch
    epoch = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
    seconds_since_epoch = int((dt - epoch).total_seconds())
    total_ns = seconds_since_epoch * 10**9 + nano_frac
    return total_ns


def multiline_command(command: str, ignore_contains: Optional[str] = None) -> str:
    """
    Format a command to be multiline
    """
    print(f"Running shell command : {Colors.YELLOW}{command}{Colors.ENDC}")
    # Tokenize the command preserving spaces inside quotes
    tokens = shlex.split(command)

    # Assume the command starts with "docker build"
    if len(tokens) < 2:
        return command

    # Start with the base command (first two tokens)
    first_line = []
    i = 0
    for token in tokens:
        if token.startswith("-"):
            break

        i += 1
        first_line.append(token)

    lines = [f"{' '.join(first_line)} \\"]

    while i < len(tokens):
        token = tokens[i]
        # If token is a flag and next token exists and doesn't start with '-', join them.
        if (
            token.startswith("-")
            and (i + 1) < len(tokens)
            and not tokens[i + 1].startswith("-")
        ):
            next_token = tokens[i + 1]
            if ignore_contains is None or ignore_contains not in next_token:
                next_token = shlex.quote(next_token)
            line = f"\t{token} {next_token} \\"
            i += 2
        else:
            line = f"\t{token} \\"
            i += 1
        lines.append(line)

    # Remove the trailing backslash from the last line
    lines[-1] = lines[-1].rstrip(" \\")
    return "\n".join(lines)


def dict_sha256sum(d: dict) -> str:
    serialized = json.dumps(d, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode()).hexdigest()


def replace_placeholders(text: str, replacements: dict[str, str], placeholder: str):
    """
    Replaces placeholders in the format {{placeholder.value}} with predefined values.

    Only replaces variable names that match the regex: `^[A-Za-z_][A-Za-z0-9_]*$`
    ex: `hello_world` `VARIABLE_NAME`

    :param text: The input string containing placeholders.
    :param replacements: A dictionary mapping variable names to their replacement values.
    :return: The modified string with replacements applied.
    """
    pattern = r"\{\{" + re.escape(placeholder) + r"\.([A-Za-z_][A-Za-z0-9_]*)\}\}"

    def replacer(match: re.Match[str]):
        var_name = match.group(1)
        return replacements.get(var_name, match.group(0))  # Keep original if not found

    return re.sub(pattern, replacer, text)


def replace_multiple_placeholders(text: str, replacements: dict) -> str:
    """
    Replaces placeholders in the format {{key.subkey}} with values from nested dictionaries.
    Example:
        replace_placeholders("{{k.v}} {{a.b}}", dict(k={"v": "hello"}, a={"b": world}))
        -> "hello world"
    """
    pattern = r"\{\{([A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*)\}\}"

    def replacer(match: re.Match[str]):
        keys = match.group(1).split(".")
        value = replacements
        for k in keys:
            if not isinstance(value, dict) or k not in value:
                return match.group(0)  # keep original if not found
            value = value[k]
        return str(value)

    return re.sub(pattern, replacer, text)
