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
    from zane_api.models import Deployment, Environment, GitApp
    from zane_api.constants import HEAD_COMMIT
    from ..helpers import (
        deployment_log,
        get_docker_client,
        get_resource_labels,
        get_env_network_resource_name,
        generate_caddyfile_for_static_website,
        get_buildkit_builder_resource_name,
        get_build_environment_variables_for_deployment,
        get_swarm_service_aliases_ips_on_network,
        get_swarm_service_name_for_deployment,
        empty_folder,
    )


from ..shared import ComposeStackDeploymentDetails


class ComposeStackActivities:
    def __init__(self):
        self.docker_client = get_docker_client()

    @activity.defn
    async def create_temporary_directory_for_build(
        self, deployment: ComposeStackDeploymentDetails
    ) -> str:
        # await deployment_log(
        #     deployment=deployment,
        #     message="Creating temporary directory for building the app...",
        #     source=RuntimeLogSource.BUILD,
        # )
        temp_dir = tempfile.mkdtemp()
        # await deployment_log(
        #     deployment=deployment,
        #     message=f"Temporary build directory created at {Colors.ORANGE}{temp_dir}{Colors.ENDC} ✅",
        #     source=RuntimeLogSource.BUILD,
        # )
        return temp_dir

    @activity.defn
    async def prepare_deployment(
        self,
        deployment: ComposeStackDeploymentDetails,
    ):
        pass

    @activity.defn
    async def deploy_stack(
        self,
        deployment: ComposeStackDeploymentDetails,
    ):
        pass

    @activity.defn
    async def monitor_stack_health(
        self,
        deployment: ComposeStackDeploymentDetails,
    ):
        pass

    @activity.defn
    async def finalize_deployment(
        self,
        deployment: ComposeStackDeploymentDetails,
    ):
        pass
