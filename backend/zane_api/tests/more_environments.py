from datetime import timedelta
from typing import cast
from urllib.parse import urlencode
from .base import AuthAPITestCase
from django.urls import reverse
from rest_framework import status

from ..models import (
    Project,
    Deployment,
    Service,
    Environment,
    DeploymentChange,
    PreviewEnvMetadata,
    GitApp,
    PreviewEnvTemplate,
    SharedTemplateEnvVariable,
    SharedEnvVariable,
    URL,
)

from django.conf import settings

from ..utils import jprint, find_item_in_sequence


class MoreEnvironmentViewTests(AuthAPITestCase):
    async def test_deployed_services_are_added_with_global_alias_using_env_id_as_suffix(
        self,
    ):
        p, service = await self.acreate_and_deploy_redis_docker_service()

        deployment = cast(Deployment, await service.deployments.afirst())
        fake_service = self.fake_docker_client.get_deployment_service(deployment)
        global_network_config = find_item_in_sequence(lambda net: net["Target"] == "zane", fake_service.networks)  # type: ignore

        global_aliases = [
            alias
            for alias in global_network_config["Aliases"]  # type: ignore
            if "blue" not in alias and "green" not in alias
        ]
        self.assertEqual(2, len(global_aliases))

    def test_clone_environment_with_unsaved_changes_copy_the_changes_to_new_service(
        self,
    ):
        self.assertTrue(False)
