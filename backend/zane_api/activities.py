from temporalio import activity

from .models import Project
from .serializers import ProjectSerializer
from .shared import HelloPayload, DeployPayload


@activity.defn
async def greet(payload: HelloPayload) -> str:
    return f"Hello, {payload.name}!"


@activity.defn
async def say_goodbye(payload: HelloPayload) -> str:
    return f"bye, {payload.name}!"


@activity.defn
async def get_project(payload: DeployPayload) -> dict:
    print(f"Running `get_project(payload={payload})`")
    project = await Project.objects.aget(slug=payload.slug)
    return ProjectSerializer(project).data
