from django.conf import settings

from zane_api.tests.base import AuthAPITestCase
from zane_api.models import Project
from temporal.shared import (
    HealthcheckDeploymentDetails,
    SimpleDeploymentDetails,
)
from django.urls import reverse
from rest_framework import status
from zane_api.utils import jprint


class MonorepoDeploymentViewTests(AuthAPITestCase):
    def test_regenerate_project_deploy_token(self):
        user = self.loginUser()
        project = Project.objects.create(slug="zaneops", owner=user)
        response = self.client.patch(
            reverse(
                "zane_api:projects.regenerate_deploy_token",
                kwargs={"project_slug": project.slug},
            ),
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        project.refresh_from_db()
        self.assertIsNotNone(project.deploy_token)

    def test_create_project_generate_deploy_token(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zaneops"},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        project = Project.objects.get(slug="zaneops")

        self.assertIsNotNone(project.deploy_token)

    def test_webhook_deploy_project(self):
        _, serviceA = self.create_and_deploy_git_service(slug="docs")
        project, serviceB = self.create_and_deploy_git_service(slug="templates")

        response = self.client.put(
            reverse(
                "zane_api:projects.trigger_monorepo_preview",
                kwargs={"deploy_token": project.deploy_token},
            ),
        )
        self.assertEqual(status.HTTP_202_ACCEPTED, response.status_code)
        deployment_count_serviceA = serviceA.deployments.count()
        deployment_count_serviceB = serviceB.deployments.count()

        self.assertEqual(2, deployment_count_serviceA)
        self.assertEqual(2, deployment_count_serviceB)
