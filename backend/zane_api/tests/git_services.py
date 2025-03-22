# type: ignore
from .base import AuthAPITestCase
from django.urls import reverse
from rest_framework import status

from ..models import (
    Project,
    Service,
    Deployment,
    DeploymentChange,
)


class CreateGitServiceViewTests(AuthAPITestCase):
    def test_create_git_service(self):
        # services.git.create
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        p = Project.objects.get(slug="zane-ops")

        create_service_payload = {
            "slug": "docs",
            "repository_url": "https://github.com/zane-ops/docs",
            "branch_name": "main",
        }

        response = self.client.post(
            reverse(
                "zane_api:services.git.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        data = response.json()
        self.assertIsNotNone(data)

        created_service: Service = Service.objects.filter(
            slug="docs", type=Service.ServiceType.GIT_REPOSITORY
        ).first()
        self.assertIsNotNone(created_service)
        # self.assertEqual("main", created_service.branch_name)
        # self.assertEqual("https://github.com/zane-ops/docs", created_service.repository_url)
