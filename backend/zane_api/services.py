from typing import Dict, List, TypedDict

import docker

from .models import Project


class DockerImageResultFromSearch(TypedDict):
    name: str
    description: str
    is_official: bool


class DockerService:
    instance = None  # type: DockerService | None
    client: docker.DockerClient | None = None
    DOCKER_HUB_REGISTRY_URL = 'registry-1.docker.io/v2'

    @classmethod
    def _get_instance(cls):
        if cls.instance is None:
            cls.instance = DockerService()
            cls.client = docker.from_env()
        return cls.instance

    @classmethod
    def search_registry(cls, term: str) -> List[DockerImageResultFromSearch]:
        """
        List all images in registry starting with a certain term.
        """
        instance = cls._get_instance()
        return instance.client.images.search(term=term, limit=30)

    @classmethod
    def login(cls, username: str, password: str, registry_url: str = DOCKER_HUB_REGISTRY_URL) -> bool:
        """
        List all images in registry starting with a certain term.
        """
        instance = cls._get_instance()
        try:
            instance.client.login(username, password, registry_url, reauth=True)
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
        instance = cls._get_instance()

        try:
            network_associated_to_project = instance.client.networks.get(
                f"{project.slug}-{project.created_at.timestamp()}"
            )
            network_associated_to_project.remove()
        except docker.errors.NotFound:
            # We will assume the network has been deleted before
            pass
        return None

    @classmethod
    def create_project_resources(cls, project: Project):
        instance = cls._get_instance()
        instance.client.networks.create(f"{project.slug}-{project.created_at.timestamp()}")

    @classmethod
    def check_if_port_is_available(cls, port: int) -> bool:
        instance = cls._get_instance()
        try:
            instance.client.containers.run(
                image='nginx:alpine-perl',
                ports={'80/tcp': ('0.0.0.0', port)},
                command="echo hello world",
                remove=True
            )
            return True
        except docker.errors.APIError:
            return False
