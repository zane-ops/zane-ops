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
from ..utils import jprint


class CreateGitServiceViewTests(AuthAPITestCase):
    def test_create_simple_git_service(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        p = Project.objects.get(slug="zane-ops")

        create_service_payload = {
            "slug": "docs",
            "repository_url": "https://github.com/zaneops/docs",
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

    def test_create_git_service_bad_request(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        p = Project.objects.get(slug="zane-ops")

        create_service_payload = {
            "slug": "docs",
            "image": "ghcr.io/zane-ops/docs",
        }

        response = self.client.post(
            reverse(
                "zane_api:services.git.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_create_git_service_with_non_existent_repository_fails(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        p = Project.objects.get(slug="zane-ops")

        create_service_payload = {
            "slug": "docs",
            "repository_url": self.fake_git.NON_EXISTENT_REPOSITORY,
            "branch_name": "main",
        }

        response = self.client.post(
            reverse(
                "zane_api:services.git.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_create_git_service_with_non_existent_branch_fails(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        p = Project.objects.get(slug="zane-ops")

        create_service_payload = {
            "slug": "docs",
            "repository_url": "https://github.com/zaneops/docs",
            "branch_name": self.fake_git.NON_EXISTENT_BRANCH,
        }

        response = self.client.post(
            reverse(
                "zane_api:services.git.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_creating_git_service_should_create_changes(self):
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
            "dockerfile_path": "./app/prod.Dockerfile",
            "build_context_dir": "./app",
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
        source_change: DeploymentChange = DeploymentChange.objects.filter(
            service=created_service, field=DeploymentChange.ChangeField.SOURCE
        ).first()
        self.assertIsNotNone(source_change)
        self.assertEqual(
            {
                "branch_name": "main",
                "commit_sha": "HEAD",
                "repository_url": "https://github.com/zane-ops/docs",
                "builder": "DOCKERFILE",
                "dockerfile_builder_options": {
                    "dockerfile_path": "./app/prod.Dockerfile",
                    "build_context_dir": "./app",
                },
            },
            source_change.new_value,
        )


class DeployGitServiceViewTests(AuthAPITestCase):
    def test_deploy_service_apply_pending_changes(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        p = Project.objects.get(slug="zane-ops")

        create_service_payload = {
            "slug": "docs",
            "repository_url": "https://github.com/zaneops/docs",
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

        service: Service = Service.objects.filter(
            slug="docs", type=Service.ServiceType.GIT_REPOSITORY
        ).first()

        response = self.client.put(
            reverse(
                "zane_api:services.git.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            )
        )
        service.refresh_from_db()
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual("https://github.com/zaneops/docs", service.repository_url)
        self.assertEqual("main", service.branch_name)
        self.assertEqual(Service.Builder.DOCKERFILE, service.builder)
        self.assertEqual(
            {
                "dockerfile_path": "./Dockerfile",
                "build_context_dir": "./",
            },
            service.dockerfile_builder_options,
        )

    def test_deploy_simple_service_create_deployment_with_commit_sha(self):
        p, service = self.create_git_service()

        response = self.client.put(
            reverse(
                "zane_api:services.git.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            )
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        self.assertEqual(1, service.deployments.count())

        latest_deployment: Deployment = service.deployments.first()
        self.assertIsNotNone(latest_deployment.commit_sha)
        self.assertNotEqual("HEAD", latest_deployment.commit_sha)


class ProjectServiceListWithGitServicesViewTests(AuthAPITestCase):
    def test_show_git_resources(self):
        self.create_git_service()
        p, _ = self.create_redis_docker_service()

        response = self.client.get(
            reverse(
                "zane_api:projects.service_list",
                kwargs={"slug": p.slug, "env_slug": "production"},
            )
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertTrue(type(response.json()) is list)
        self.assertEqual(2, len(response.json()))
