from dataclasses import dataclass
from typing import List


@dataclass
class ProjectDetails:
    id: str


@dataclass
class ArchivedProjectDetails:
    id: int
    original_id: str


@dataclass
class URLDto:
    domain: str
    base_path: str
    strip_prefix: bool


@dataclass
class ArchivedServiceDetails:
    urls: List[URLDto]
    deployment_urls: List[str]
    deployments: List["DeploymentDetails"]


@dataclass
class DeploymentDetails:
    id: str
    project_id: str
    service_id: str
