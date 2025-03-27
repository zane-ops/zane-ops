import datetime
from typing import Any, Dict, List, Literal, Optional
from dataclasses import dataclass

from zane_api.utils import iso_to_ns


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
    deployment_id: Optional[str] = None
    content: Optional[str] = None
    content_text: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        return cls(**data)

    def to_dict(self):
        return {
            "service_id": self.service_id,
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

    def to_es_dict(self):
        return {
            "service_id": self.service_id,
            "deployment_id": self.deployment_id,
            "time": (
                self.time.isoformat()
                if isinstance(self.time, datetime.datetime)
                else self.time
            ),
            "created_at": (
                self.created_at.isoformat()
                if isinstance(self.created_at, datetime.datetime)
                else self.created_at
            ),
            "content": {
                "text": self.content_text,
                "raw": self.content,
            },
            "level": self.level,
            "source": self.source,
        }
