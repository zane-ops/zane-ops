import datetime
from typing import Any, Dict, List, Literal, Optional
from dataclasses import dataclass

from zane_api.utils import iso_to_ns
from django.conf import settings


class RuntimeLogLevel:
    ERROR = "ERROR"
    INFO = "INFO"


class RuntimeLogSource:
    SYSTEM = "SYSTEM"
    SERVICE = "SERVICE"
    BUILD = "BUILD"


@dataclass
class LiveRuntimeLogQueryDto:
    deployment_id: str
    start: datetime.datetime
    sources: List[str]


@dataclass
class RuntimeLogDto:
    time: str | datetime.datetime
    level: Literal["ERROR", "INFO"]
    source: Literal["SYSTEM", "SERVICE", "BUILD"]
    id: Optional[str] = None
    created_at: Optional[str | datetime.datetime] = None
    service_id: Optional[str] = None
    stack_id: Optional[str] = None
    deployment_id: Optional[str] = None
    stack_service_name: Optional[str] = None
    content: Optional[str] = None
    content_text: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        return cls(**data)

    def to_dict(self):
        return {
            "service_id": self.service_id,
            "stack_id": self.stack_id,
            "stack_service_name": self.stack_service_name,
            "deployment_id": self.deployment_id,
            "time": (
                int(self.time.timestamp() * 10**9)
                if isinstance(self.time, datetime.datetime)
                else iso_to_ns(self.time)
            ),  # multiply to nanoseconds
            "created_at": (
                self.created_at.isoformat()
                if isinstance(self.created_at, datetime.datetime)
                else self.created_at
            ),
            "content_text": self.content_text,
            "content": self.content,
            "level": self.level,
            "source": self.source,
        }

    @property
    def loki_labels(self):
        return {
            # for managed services
            "service_id": self.service_id or "unknown",
            "deployment_id": self.deployment_id or "unknown",
            # for compose stacks
            "stack_id": self.stack_id or "unknown",
            "stack_service_name": self.stack_service_name or "unknown",
            # common args
            "level": self.level,
            "source": self.source,
            "app": f"{settings.LOKI_APP_NAME}",
        }
