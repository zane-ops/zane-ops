import datetime
from dataclasses import dataclass
from enum import Enum


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
                ExitCode=container_status_data["ExitCode"]
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
