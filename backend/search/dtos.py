from typing import Any, Dict, Literal, Optional
from dataclasses import dataclass


class RuntimeLogLevel:
    ERROR = "ERROR"
    INFO = "INFO"


class RuntimeLogSource:
    SYSTEM = "SYSTEM"
    SERVICE = "SERVICE"


@dataclass
class RuntimeLogDto:
    time: str
    level: Literal["ERROR", "INFO"]
    source: Literal["SYSTEM", "SERVICE"]
    id: Optional[str] = None
    service_id: Optional[str] = None
    deployment_id: Optional[str] = None
    content: Optional[str] = None
    content_text: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        return cls(**data)

    def to_dict(self):
        return {
            "id": self.id,
            "time": self.time,
            "level": self.level,
            "source": self.source,
            "service_id": self.service_id,
            "deployment_id": self.deployment_id,
            "content": self.content,
            "content_text": self.content_text,
        }

    def to_es_dict(self):
        return {
            "service_id": self.service_id,
            "deployment_id": self.deployment_id,
            "time": self.time,
            "content": {
                "text": self.content_text,
                "raw": self.content,
            },
            "level": self.level,
            "source": self.source,
        }
