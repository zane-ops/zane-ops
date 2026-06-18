"""
Seam for registering extra Temporal workflows/activities from optional apps
(e.g. the commercial EE layer) **without** the core ``temporal`` package ever
importing them.

Dependency rule (see ``ee/__init__.py``): the core must never import from
``ee/``. Instead, optional apps register their workflows/activities at startup
(in their ``AppConfig.ready``), and the worker merges them in through
``get_workflows_and_activities``. This keeps the core worker functional even
when the whole ``ee/`` directory is absent.
"""

from typing import Any, Callable, List, Optional

_extra_workflows: List[Any] = []
_extra_activities: List[Callable[..., Any]] = []


def register_workflows_and_activities(
    *,
    workflows: Optional[List[Any]] = None,
    activities: Optional[List[Callable[..., Any]]] = None,
) -> None:
    if workflows:
        _extra_workflows.extend(workflows)
    if activities:
        _extra_activities.extend(activities)


def get_extra_workflows() -> List[Any]:
    return list(_extra_workflows)


def get_extra_activities() -> List[Callable[..., Any]]:
    return list(_extra_activities)
