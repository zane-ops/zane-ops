from .base import AuthAPITestCase
from django.urls import reverse
from rest_framework import status

from ..models import Project, DockerDeployment, DockerRegistryService
from ..temporal.activities import get_env_network_resource_name


class EnvironmentTests(AuthAPITestCase):
    def test_create_default_production_env_when_creating_project(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        self.assertEqual(1, Project.objects.count())
        project = Project.objects.get(slug="zane-ops")
        self.assertIsNotNone(project.environments.filter(name="production").first())

    async def test_create_production_network_when_creating_project(self):
        await self.aLoginUser()
        response = await self.async_client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        project = await Project.objects.aget(slug="zane-ops")

        production_env = (
            await project.environments.filter(name="production")
            .select_related("project")
            .afirst()
        )
        network = self.fake_docker_client.get_env_network(production_env)  # type: ignore
        self.assertIsNotNone(network)

    async def test_archive_project_removes_all_project_environments_networks(self):
        await self.aLoginUser()
        response = await self.async_client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        project = await Project.objects.aget(slug="zane-ops")

        response = await self.async_client.delete(
            reverse("zane_api:projects.details", kwargs={"slug": project.slug})
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        self.assertEqual(0, len(self.fake_docker_client.get_project_networks(project)))

    async def test_deploy_service_to_production_env_by_default(self):
        p, service = await self.acreate_and_deploy_redis_docker_service()

        deployment: DockerDeployment = await service.deployments.afirst()  # type: ignore
        service = self.fake_docker_client.get_deployment_service(deployment=deployment)
        service_networks = {net["Target"]: net["Aliases"] for net in service.networks}  # type: ignore

        production_env = await p.aproduction_env
        self.assertTrue(
            get_env_network_resource_name(production_env.id, p.id) in service_networks
        )


class ServiceEnvironmentViewTests(AuthAPITestCase):
    def test_create_service_should_put_service_in_production_by_default(self):
        p, service = self.create_and_deploy_redis_docker_service()
        self.assertIsNotNone(service.environment)
        self.assertEqual(service.environment, p.production_env)
