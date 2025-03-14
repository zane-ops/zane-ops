from .base import AuthAPITestCase
from django.urls import reverse
from rest_framework import status

from ..models import Project, Environment


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
