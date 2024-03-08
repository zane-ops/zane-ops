from typing import Dict, List, TypedDict

import docker
import docker.errors

from .models import Project


class DockerImageResultFromRegistry(TypedDict):
    name: str
    description: str
    is_official: bool
    is_automated: bool


class DockerImageResult(TypedDict):
    full_image: str
    description: str


class DockerService:
    client: docker.DockerClient | None = None
    DOCKER_HUB_REGISTRY_URL = 'registry-1.docker.io/v2'

    @classmethod
    def _get_client(cls) -> docker.DockerClient:
        if cls.client is None:
            cls.client = docker.from_env()
        return cls.client

    @classmethod
    def search_registry(cls, term: str) -> List[DockerImageResult]:
        """
        List all images in registry starting with a certain term.
        """
        client = cls._get_client()
        result: List[DockerImageResultFromRegistry] = client.images.search(term=term, limit=30)
        images_to_return: List[DockerImageResult] = []

        for image in result:
            api_image_result = {}
            if image["is_official"]:
                api_image_result["full_image"] = f'library/{image["name"]}:latest'
            else:
                api_image_result["full_image"] = f'{image["name"]}:latest'
            api_image_result["description"] = image["description"]
            images_to_return.append(api_image_result)
        return images_to_return

    @classmethod
    def login(cls, username: str, password: str, registry_url: str = DOCKER_HUB_REGISTRY_URL) -> bool:
        """
        List all images in registry starting with a certain term.
        """
        client = cls._get_client()
        try:
            client.login(username, password, registry_url, reauth=True)
            return True
        except docker.errors.APIError:
            return False

    @classmethod
    def cleanup_project_resources(cls, project: Project) -> Dict[str, Dict[str, List[str]]] | None:
        """
        TODO : we will need to cleanup :
          - services
          - workers &
          - CRONs
          - volumes

        It returns None when everything has gone well, else it will return errors
        """
        client = cls._get_client()

        try:
            network_associated_to_project = client.networks.get(get_resource_name(project, resource_type='network'))
            network_associated_to_project.remove()
        except docker.errors.NotFound:
            # We will assume the network has been deleted before
            pass
        return None

    @classmethod
    def create_project_resources(cls, project: Project):
        client = cls._get_client()
        client.networks.create(
            name=get_resource_name(project, resource_type='network'),
            scope="swarm",
            driver="overlay",
        )

    @classmethod
    def check_if_port_is_available(cls, port: int) -> bool:
        client = cls._get_client()
        try:
            client.containers.run(
                image='nginx:alpine-perl',
                ports={'80/tcp': ('0.0.0.0', port)},
                command="echo hello world",
                remove=True
            )
            return True
        except docker.errors.APIError:
            return False


def get_resource_name(project: Project, resource_type: str) -> str:
    match resource_type:
        case 'network':
            ts_to_full_number = str(project.created_at.timestamp()).replace(".", "")
            return f"{project.slug}-{ts_to_full_number}"
        case _:
            raise ValueError(f"resource type '{resource_type}' is not supported")
