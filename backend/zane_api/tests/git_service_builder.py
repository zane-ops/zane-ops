# type: ignore
from .base import AuthAPITestCase
from django.urls import reverse
from rest_framework import status

from ..models import (
    Project,
    Service,
    Deployment,
    DeploymentChange,
    SharedEnvVariable,
    EnvVariable,
)
from ..utils import jprint


class StaticGitBuilderViewTests(AuthAPITestCase):
    def test_create_service_with_static_builder(self):
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
            "builder": Service.Builder.STATIC_DIR,
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

        builder_change: DeploymentChange = DeploymentChange.objects.filter(
            service=created_service, field=DeploymentChange.ChangeField.BUILDER
        ).first()
        self.assertIsNotNone(builder_change)

        print(f"{builder_change.new_value=}")
        self.assertEqual(
            {
                "builder": "STATIC_DIR",
                "options": {
                    "base_directory": "./",
                    "index_page": "./index.html",
                    "not_found_page": None,
                    "is_spa": False,
                },
            },
            builder_change.new_value,
        )

    def test_apply_service_static_builder_change(self):
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
            "builder": Service.Builder.STATIC_DIR,
        }

        response = self.client.post(
            reverse(
                "zane_api:services.git.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service: Service = Service.objects.filter(
            slug="docs", type=Service.ServiceType.GIT_REPOSITORY
        ).first()
        self.assertIsNotNone(created_service)

        response = self.client.put(
            reverse(
                "zane_api:services.git.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": created_service.slug,
                },
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        self.assertEqual(
            0,
            DeploymentChange.objects.filter(
                service=created_service, applied=False
            ).count(),
        )

        created_service.refresh_from_db()
        self.assertEqual(Service.Builder.STATIC_DIR, created_service.builder)
        self.assertIsNone(created_service.dockerfile_builder_options)
        self.assertIsNotNone(created_service.static_dir_builder_options)
        self.assertEqual(
            {
                "base_directory": "./",
                "index_page": "./index.html",
                "not_found_page": None,
                "is_spa": False,
            },
            created_service.static_dir_builder_options,
        )

    def test_request_service_change_with_static_dir_builder(self):
        p, service = self.create_git_service()

        changes_payload = {
            "field": DeploymentChange.ChangeField.BUILDER,
            "type": "UPDATE",
            "new_value": {
                "builder": Service.Builder.STATIC_DIR,
                "base_directory": "./dist",
                "index_page": "./index.html",
                "not_found_page": "./404.html",
                "is_spa": True,
            },
        }

        response = self.client.put(
            reverse(
                "zane_api:services.request_deployment_changes",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        change: DeploymentChange = DeploymentChange.objects.filter(
            service__slug=service.slug,
            field=DeploymentChange.ChangeField.BUILDER,
        ).first()
        self.assertIsNotNone(change)
        self.assertEqual(
            {
                "builder": Service.Builder.STATIC_DIR,
                "options": {
                    "base_directory": "./dist",
                    "index_page": "./index.html",
                    "not_found_page": "./404.html",
                    "is_spa": True,
                },
            },
            change.new_value,
        )
