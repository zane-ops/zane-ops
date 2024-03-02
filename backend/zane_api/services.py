from typing import Dict, List

from .models import Project


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
