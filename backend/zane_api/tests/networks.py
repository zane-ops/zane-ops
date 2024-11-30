from .base import AuthAPITestCase
from django.urls import reverse
from ..models import (
    Project,
    DockerDeployment,
    DockerRegistryService,
    DockerDeploymentChange,
    Volume,
    PortConfiguration,
    URL,
    HealthCheck,
    DockerEnvVariable,
)
from rest_framework import status


class DockerServiceNetworksTests(AuthAPITestCase):
    async def test_service_added_to_global_network(self):
        p, service = await self.acreate_and_deploy_redis_docker_service()

        deployment: DockerDeployment = await service.deployments.afirst()
        service = self.fake_docker_client.get_deployment_service(deployment=deployment)
        service_networks = {net["Target"]: net["Aliases"] for net in service.networks}
        self.assertTrue("zane" in service_networks)

    async def test_healthcheck_path_uses_service_id_to_run_healthcheck(self):
        p, service = await self.acreate_and_deploy_caddy_docker_service()
        self.assertTrue(False)
