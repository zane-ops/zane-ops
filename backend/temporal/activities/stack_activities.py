import asyncio
import json
import shlex
from typing import Any, List, Optional, Set, cast
from temporalio import activity, workflow
import tempfile
from temporalio.exceptions import ApplicationError
import os
import os.path
import re
import requests

from rest_framework import status

with workflow.unsafe.imports_passed_through():
    from compose.models import ComposeStack, ComposeStackDeployment
    from django.utils import timezone
    from ..helpers import (
        deployment_log,
        get_docker_client,
    )
    from search.dtos import RuntimeLogSource
    from zane_api.utils import Colors


from ..shared import ComposeStackDeploymentDetails, ComposeStackBuildDetails


class ComposeStackActivities:
    def __init__(self):
        self.docker_client = get_docker_client()

    @activity.defn
    async def prepare_deployment(self, deployment: ComposeStackDeploymentDetails):
        await deployment_log(
            deployment,
            f"Preparing compose stack deployment {Colors.ORANGE}{deployment.hash}{Colors.ENDC}...",
        )

        await ComposeStackDeployment.objects.filter(
            hash=deployment.hash,
            stack_id=deployment.stack_id,
            status=ComposeStackDeployment.DeploymentStatus.QUEUED,
        ).aupdate(
            status=ComposeStackDeployment.DeploymentStatus.DEPLOYING,
            started_at=timezone.now(),
        )

    @activity.defn
    async def create_temporary_directory_for_build(
        self,
        deployment: ComposeStackDeploymentDetails,
    ) -> str:
        await deployment_log(
            deployment=deployment,
            message="Creating temporary directory for building the app...",
            source=RuntimeLogSource.BUILD,
        )
        temp_dir = tempfile.mkdtemp()
        await deployment_log(
            deployment=deployment,
            message=f"Temporary build directory created at {Colors.ORANGE}{temp_dir}{Colors.ENDC} ✅",
            source=RuntimeLogSource.BUILD,
        )
        return temp_dir

    @activity.defn
    async def deploy_stack_with_cli(self, deployment: ComposeStackBuildDetails):
        pass

    @activity.defn
    async def monitor_stack_health(self, deployment: ComposeStackDeploymentDetails):
        pass

    @activity.defn
    async def finalize_deployment(self, deployment: ComposeStackDeploymentDetails):
        pass
