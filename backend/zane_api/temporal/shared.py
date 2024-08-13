from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from django.conf import settings

from ..dtos import URLDto, DockerServiceSnapshot


@dataclass
class ProjectDetails:
    id: str


@dataclass
class ArchivedProjectDetails:
    id: int
    original_id: str


@dataclass
class DeploymentDetails:
    hash: str
    slot: str
    auth_token: str
    unprefixed_hash: str
    queued_at: str
    service: DockerServiceSnapshot
    url: Optional[str] = None

    @property
    def queued_at_as_datetime(self):
        return datetime.fromisoformat(self.queued_at)

    @property
    def network_aliases(self):
        aliases = []
        if self.service is not None and len(self.service.network_aliases) > 0:
            aliases = self.service.network_aliases + [
                f"{self.service.network_alias}.{self.slot.lower()}.{settings.ZANE_INTERNAL_DOMAIN}",
            ]
        return aliases


@dataclass
class DeploymentHealthcheckResult:
    deployment_hash: str
    status: str
    reason: Optional[str] = None


@dataclass
class ArchivedDeploymentDetails:
    id: str
    project_id: str
    service_id: str


@dataclass
class ArchivedServiceDetails:
    urls: List[URLDto]
    deployment_urls: List[str]
    deployments: List[ArchivedDeploymentDetails]
