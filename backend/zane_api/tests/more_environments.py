from typing import cast
from .base import AuthAPITestCase
from django.urls import reverse
from rest_framework import status

from ..models import (
    Deployment,
    Environment,
    DeploymentChange,
)

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
        p, service = self.create_caddy_docker_service()
        response = self.client.post(
            reverse(
                "zane_api:projects.environment.clone",
                kwargs={"slug": p.slug, "env_slug": Environment.PRODUCTION_ENV},
            ),
            data={"name": "staging"},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        staging_env = p.environments.get(name="staging")

        services_in_staging = staging_env.services
        self.assertEqual(1, services_in_staging.count())

        cloned_caddy_service = services_in_staging.get(slug=service.slug)
        self.assertIsNotNone(
            cloned_caddy_service.unapplied_changes.filter(
                field=DeploymentChange.ChangeField.SOURCE
            ).first()
        )

    def test_clone_environment_with_unsaved_changes_and_deploy_apply_new_changes(
        self,
    ):
        p, service = self.create_caddy_docker_service()
        response = self.client.post(
            reverse(
                "zane_api:projects.environment.clone",
                kwargs={"slug": p.slug, "env_slug": Environment.PRODUCTION_ENV},
            ),
            data={"name": "staging", "deploy_services": True},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        staging_env = p.environments.get(name="staging")

        services_in_staging = staging_env.services
        self.assertEqual(1, services_in_staging.count())

        cloned_caddy_service = services_in_staging.get(slug=service.slug)
        self.assertIsNotNone(cloned_caddy_service.image)
