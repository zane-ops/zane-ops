import dataclasses
import datetime
import json
import random
import string
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import Callable, TypeVar, List, Optional, Literal

from django.core.cache import cache


def cache_result(ttl: int = None, cache_key: str = None):
    def decorator(func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            # Generate a cache key if not provided
            key = (
                cache_key
                or f"{func.__name__}_{'_'.join(map(str, args))}_{'_'.join(f'{k}_{v}' for k, v in kwargs.items())}"
            )

            # Try to get the result from the cache
            result = cache.get(key)
            if result is None:
                # If cache miss, call the function and cache the result
                result = func(*args, **kwargs)
                cache.set(key, result, ttl)
            return result

        return wrapped

    return decorator


def strip_slash_if_exists(
    url: str,
    strip_end: bool = False,
    strip_start: bool = True,
):
    final_url = url
    if strip_start and url.startswith("/"):
        final_url = final_url[1:]
    if strip_end and url.endswith("/"):
        final_url = final_url[:-1]
    return final_url


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
        version = Version(**data["Version"])
        status_data = data["Status"]
        container_status: None | ContainerStatus = None
        container_status_data = data["Status"].get("ContainerStatus")
        if container_status_data is not None:
            container_status = ContainerStatus(
                ExitCode=container_status_data["ExitCode"],
                ContainerID=container_status_data.get("ContainerID"),
            )

        task_status = Status(
            Timestamp=status_data["Timestamp"],
            State=DockerSwarmTaskState(status_data["State"]),
            Message=status_data["Message"],
            ContainerStatus=container_status,
            Err=status_data.get("Err"),
        )
        return DockerSwarmTask(
            ID=data["ID"],
            Version=version,
            CreatedAt=data["CreatedAt"],
            UpdatedAt=data["UpdatedAt"],
            Status=task_status,
            DesiredState=DockerSwarmTaskState(data["DesiredState"]),
        )


class LockAcquisitionError(Exception):
    """Exception raised when a lock cannot be acquired."""

    def __init__(self, message: str, countdown: int):
        super().__init__(message)
        self.countdown = countdown


@contextmanager
def cache_lock(lock_id: str, timeout=60, margin: int = 5):
    lock_key = f"{lock_id}_lock"
    # Attempt to acquire the lock
    if not cache.add(lock_key, "true", timeout=timeout):  # Lock expires in 60 seconds
        remaining_ttl = cache.ttl(lock_key) or timeout
        countdown = remaining_ttl + margin
        raise LockAcquisitionError(
            f"Failed to acquire lock for {lock_id}", countdown=countdown
        )

    try:
        yield True
    finally:
        cache.delete(lock_key)  # Release the lock


def format_seconds(seconds: float):
    seconds = round(seconds)  # Round to the nearest integer
    minutes = seconds // 60
    remaining_seconds = seconds % 60
    if minutes > 0:
        return f"{minutes}m{remaining_seconds:02}s"
    else:
        return f"{remaining_seconds}s"


def convert_value_to_bytes(
    value: int,
    unit: Literal["BYTES", "KILOBYTES", "MEGABYTES", "GIGABYTES"] = "BYTES",
):
    match unit:
        case "BYTES":
            return value
        case "KILOBYTES":
            return value * 1024
        case "MEGABYTES":
            return value * 1024 * 1024
        case "GIGABYTES":
            return value * 1024 * 1024 * 1024
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


def jprint(value: dict | list | str | int | float):
    """
    Print & format value as JSON
    """
    return print(json.dumps(value, indent=2, cls=EnhancedJSONEncoder))


T = TypeVar("T")


def find_item_in_list(predicate: Callable[[T], bool], sequence: List[T]) -> Optional[T]:
    return next(
        (item for item in sequence if predicate(item)),
        None,
    )


class EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        return super().default(o)


def random_word(length: int = 10):
    letters = string.ascii_lowercase
    return "".join(random.choice(letters) for _ in range(length))


class Colors:
    GREEN = "\033[92m"
    BLUE = "\033[94m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    ENDC = "\033[0m"  # Reset to default color
