from typing import Dict, List, TypedDict

import docker

from .models import Project


class DockerImageResultFromSearch(TypedDict):
    name: str
    description: str
    is_official: bool


class DockerService:
    instance = None  # type: DockerService | None
    client: docker.DockerClient

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
    def login(cls, username: str, password: str, registry_url: str = 'registry-1.docker.io/v2') -> bool:
        """
        List all images in registry starting with a certain term.
        """
        instance = cls._get_instance()
        try:
            instance.client.login(username, password, registry_url)
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
        return None
