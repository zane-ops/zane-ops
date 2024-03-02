from typing import Dict, List

import docker

from .models import Project

docker_client = docker.from_env()


def cleanup_project_resources(project: Project) -> Dict[str, Dict[str, List[str]]] | None:
    """
    TODO : we will need to cleanup :
      - services
      - workers &
      - CRONs
      - volumes

    It returns None when everything has gone well, else it will return errors
    """
    return None
