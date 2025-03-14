import dataclasses
import datetime
import json
import random
import string
import re
import logging
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import (
    Any,
    Callable,
    TypeVar,
    List,
    Optional,
    Literal,
    Dict,
    Union,
    Sequence,
)
from django.core.cache import cache

# Get the logger for this module
logger = logging.getLogger(__name__)

T = TypeVar("T")


def cache_result(ttl: Optional[int] = None, cache_key: Optional[str] = None):
    """
    Decorator to cache the result of a function.

    Args:
        ttl: Time-to-live in seconds for the cache entry. If None, the default cache TTL is used.
        cache_key: Optional cache key. If None, a key is generated based on the function name and arguments.
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapped(*args: Any, **kwargs: Any) -> T:
            # Generate a cache key if not provided
            try:
                key = (
                    cache_key
                    or f"{func.__name__}_{'_'.join(map(str, args))}_{'_'.join(f'{k}_{v}' for k, v in kwargs.items())}"
                )

                # Try to get the result from the cache
                result: Optional[T] = cache.get(key)
                if result is None:
                    # If cache miss, call the function and cache the result
                    result = func(*args, **kwargs)
                    cache.set(key, result, ttl)
                    logger.debug(f"Cached result for key: {key}")
                else:
                    logger.debug(f"Retrieved result from cache for key: {key}")
                return result
            except Exception as e:
                logger.exception(f"Error during caching: {e}")
                # In case of any exception return the original function's response
                return func(*args, **kwargs)

        return wrapped

    return decorator


def strip_slash_if_exists(
    url: str,
    strip_end: bool = False,
    strip_start: bool = True,
) -> str:
    """
    Strips leading and/or trailing slashes from a URL.

    Args:
        url: The URL to strip.
        strip_end: Whether to strip trailing slashes.
        strip_start: Whether to strip leading slashes.

    Returns:
        The stripped URL.
    """
    final_url = url
    if strip_start and url.startswith("/"):
        final_url = final_url[1:]
    if strip_end and url.endswith("/"):
        final_url = final_url[:-1]
    return final_url


def datetime_to_timestamp_string(date: datetime.datetime) -> str:
    """
    Converts a datetime object to a timestamp string.

    Args:
        date: The datetime object to convert.

    Returns:
        A string representation of the timestamp.
    """
    return str(date.timestamp()).replace(".", "")


class DockerSwarmTaskState(Enum):
    """
    Enum representing the possible states of a Docker Swarm task.
    """

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
    """
    Data class representing the version of a Docker Swarm task.
    """

    Index: int


@dataclass
class ContainerStatus:
    """
    Data class representing the container status of a Docker Swarm task.
    """

    ExitCode: int
    ContainerID: Optional[str]


@dataclass
class Status:
    """
    Data class representing the status of a Docker Swarm task.
    """

    Timestamp: str
    State: DockerSwarmTaskState
    Message: str
    Err: Optional[str]
    ContainerStatus: Optional[ContainerStatus]


@dataclass
class DockerSwarmTask:
    """
    Data class representing a Docker Swarm task.
    """

    ID: str
    Version: Version
    CreatedAt: str
    UpdatedAt: str
    Status: Status
    DesiredState: DockerSwarmTaskState

    @property
    def container_id(self) -> Optional[str]:
        """
        Returns the container ID of the task, if available.
        """
        return self.Status.ContainerStatus.ContainerID if self.Status.ContainerStatus else None

    @property
    def state(self) -> DockerSwarmTaskState:
        """
        Returns the current state of the task.
        """
        return self.Status.State

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DockerSwarmTask":
        """
        Creates a DockerSwarmTask from a dictionary.

        Args:
            data: The dictionary containing the task data.

        Returns:
            A DockerSwarmTask instance.
        """
        try:
            version = Version(**data["Version"])
            status_data = data["Status"]

            container_status_data = status_data.get("ContainerStatus")
            container_status = (
                ContainerStatus(
                    ExitCode=container_status_data["ExitCode"],
                    ContainerID=container_status_data.get("ContainerID"),
                )
                if container_status_data
                else None
            )

            task_status = Status(
                Timestamp=status_data["Timestamp"],
                State=DockerSwarmTaskState(status_data["State"]),
                Message=status_data["Message"],
                Err=status_data.get("Err"),
                ContainerStatus=container_status,
            )
            return DockerSwarmTask(
                ID=data["ID"],
                Version=version,
                CreatedAt=data["CreatedAt"],
                UpdatedAt=data["UpdatedAt"],
                Status=task_status,
                DesiredState=DockerSwarmTaskState(data["DesiredState"]),
            )
        except KeyError as e:
            logger.error(f"Missing key in DockerSwarmTask data: {e}")
            raise
        except Exception as e:
            logger.exception(f"Error creating DockerSwarmTask from dict: {e}")
            raise


class LockAcquisitionError(Exception):
    """
    Exception raised when a lock cannot be acquired.
    """

    def __init__(self, message: str, countdown: int):
        super().__init__(message)
        self.countdown = countdown


def format_seconds(seconds: float) -> str:
    """
    Formats a duration in seconds into a human-readable string (e.g., "1m30s").

    Args:
        seconds: The duration in seconds.

    Returns:
        A formatted string representing the duration.
    """
    seconds = round(seconds)  # Round to the nearest integer
    minutes = seconds // 60
    remaining_seconds = seconds % 60
    if minutes > 0:
        return f"{minutes}m{remaining_seconds:02}s"
    else:
        return f"{remaining_seconds}s"


def convert_value_to_bytes(
    value: float,
    unit: Literal["BYTES", "KILOBYTES", "MEGABYTES", "GIGABYTES"] = "BYTES",
) -> int:
    """
    Converts a value to bytes based on the specified unit.

    Args:
        value: The value to convert.
        unit: The unit of the value.

    Returns:
        The value in bytes.

    Raises:
        ValueError: If the unit is invalid.
    """
    try:
        if unit == "BYTES":
            return int(value)
        elif unit == "KILOBYTES":
            return int(value * 1024)
        elif unit == "MEGABYTES":
            return int(value * 1024 * 1024)
        elif unit == "GIGABYTES":
            return int(value * 1024 * 1024 * 1024)
        else:
            raise ValueError(f"Unit `{unit}` is not valid.")
    except ValueError as e:
        logger.error(f"Error converting value to bytes: {e}")
        raise


def format_storage_value(value: int) -> str:
    """
    Formats a storage value in bytes into a human-readable string (e.g., "1.00 kb", "2.50 gb").

    Args:
        value: The storage value in bytes.

    Returns:
        A formatted string representing the storage value.
    """
    kb = 1024
    mb = 1024 * kb
    gb = 1024 * mb

    if value < kb:
        return f"{value} bytes"
    elif value < mb:
        return f"{value / kb:.2f} kb"
    elif value < gb:
        return f"{value / mb:.2f} mb"
    else:
        return f"{value / gb:.2f} gb"


def jprint(value: Any) -> None:
    """
    Print & format value as JSON.

    Args:
        value: The value to print.
    """
    print(json.dumps(value, indent=2, cls=EnhancedJSONEncoder))


def find_item_in_list(
    predicate: Callable[[T], bool], sequence: Sequence[T]
) -> Optional[T]:
    """
    Finds the first item in a sequence that satisfies a given predicate.

    Args:
        predicate: A function that takes an item from the sequence and returns a boolean.
        sequence: The sequence to search.

    Returns:
        The first item that satisfies the predicate, or None if no such item is found.
    """
    return next((item for item in sequence if predicate(item)), None)


class EnhancedJSONEncoder(json.JSONEncoder):
    """
    JSONEncoder that handles dataclasses.
    """

    def default(self, o: Any) -> Any:
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        return super().default(o)


def random_word(length: int = 10) -> str:
    """
    Generates a random lowercase word of the specified length.

    Args:
        length: The length of the word to generate.

    Returns:
        A random lowercase word.
    """
    letters = string.ascii_lowercase
    return "".join(random.choice(letters) for _ in range(length))


def generate_random_chars(length: int) -> str:
    """
    Generates a random string of letters and digits of the specified length.

    Args:
        length: The length of the string to generate.

    Returns:
        A random string of letters and digits.
    """
    letters = string.ascii_letters + string.digits
    return "".join(random.choice(letters) for _ in range(length))


class Colors:
    """
    ANSI color codes for terminal output.
    """

    GREEN = "\033[92m"
    BLUE = "\033[94m"
    ORANGE = "\033[38;5;208m"
    RED = "\033[91m"
    GREY = "\033[90m"
    ENDC = "\033[0m"  # Reset to default color


def escape_ansi(content: str) -> str:
    """
    Removes ANSI escape codes from a string.

    Args:
        content: The string to escape.

    Returns:
        The string with ANSI escape codes removed.
    """
    ANSI_ESCAPE_PATTERN = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ANSI_ESCAPE_PATTERN.sub("", content)


def excerpt(text: str, max_length: int) -> str:
    """
    Truncates a string to a maximum length, adding an ellipsis if necessary.

    Args:
        text: The string to truncate.
        max_length: The maximum length of the truncated string.

    Returns:
        The truncated string.
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - 3].rstrip() + "..."


def truncate_utf8(utf8_string: str, limit: int) -> List[str]:
    """
    Splits a UTF-8 string into chunks of specified byte size limit while preserving UTF-8 character boundaries.

    This function takes a string and splits it into multiple parts, ensuring that each part's UTF-8 encoded
    byte length does not exceed the specified limit and that no UTF-8 characters are split across chunks.

    Args:
        utf8_string: The input string to be truncated/split
        limit: Maximum number of bytes allowed in each chunk

    Returns:
        A list of string chunks, where each chunk's UTF-8 encoded form is within the byte limit
    """
    result: List[str] = []
    remaining = utf8_string

    while remaining:
        encoded = remaining.encode("utf-8")

        if len(encoded) <= limit:
            result.append(remaining)
            break

        valid_end = limit
        while valid_end > 0 and (encoded[valid_end] & 0b11000000) == 0b10000000:
            valid_end -= 1

        truncated = encoded[:valid_end].decode("utf-8", errors="ignore")
        remaining = encoded[valid_end:].decode("utf-8", errors="ignore")

        result.append(truncated)

    return result


def iso_to_ns(iso_string: str) -> int:
    """
    Convert an ISO datetime string with nanosecond precision to a timestamp in nanoseconds.

    Args:
        iso_string: ISO datetime string with nanoseconds, e.g. "2025-03-04T17:37:00.033944066+0000"

    Returns:
        Timestamp in nanoseconds since the Unix epoch.

    Raises:
        ValueError: If the input string is not in the expected ISO datetime format.
    """
    # Split into datetime part, fractional seconds, and timezone offset
    match = re.match(r"(.*?)(\.\d+)?([+-]\d{4})$", iso_string)
    if not match:
        try:
            return int(datetime.datetime.fromisoformat(iso_string).timestamp() * 1e9)
        except ValueError as e:
            logger.error(f"Invalid ISO format: {iso_string}")
            raise e

    main_part, frac, tz_str = match.group(1), match.group(2), match.group(3)
    frac = frac if frac else ".0"

    # Parse datetime ignoring fractional seconds
    try:
        dt = datetime.datetime.strptime(main_part + tz_str, "%Y-%m-%dT%H:%M:%S%z")
    except ValueError as e:
        logger.error(f"Invalid ISO format: {iso_string}")
        raise e

    # Ensure fractional seconds have exactly 9 digits (nanosecond precision)
    frac_digits = frac[1:].ljust(9, "0")[:9]
    nano_frac = int(frac_digits)

    # Calculate total nanoseconds since Unix epoch
    epoch = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
    seconds_since_epoch = int((dt - epoch).total_seconds())
    total_ns = seconds_since_epoch * 10**9 + nano_frac
    return total_ns
