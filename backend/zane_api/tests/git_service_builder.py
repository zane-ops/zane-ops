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
from ..temporal.helpers import generate_caddyfile_for_static_website
from ..dtos import StaticDirectoryBuilderOptions


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
                    "custom_caddyfile": None,
                    "generated_caddyfile": generate_caddyfile_for_static_website(
                        StaticDirectoryBuilderOptions.from_dict(
                            {
                                "base_directory": "./",
                                "index_page": "./index.html",
                            }
                        )
                    ),
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
        jprint(response.json())
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
                "generated_caddyfile": generate_caddyfile_for_static_website(
                    StaticDirectoryBuilderOptions.from_dict(
                        {
                            "base_directory": "./",
                            "index_page": "./index.html",
                        }
                    )
                ),
                "custom_caddyfile": None,
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
                    "custom_caddyfile": None,
                    "generated_caddyfile": generate_caddyfile_for_static_website(
                        StaticDirectoryBuilderOptions.from_dict(
                            {
                                "base_directory": "./dist",
                                "index_page": "./index.html",
                                "not_found_page": "./404.html",
                                "is_spa": True,
                            }
                        )
                    ),
                },
            },
            change.new_value,
        )

    def test_request_service_change_with_custom_caddyfile_uses_custom_caddyfile(self):
        p, service = self.create_git_service()

        custom_caddyfile = (
            ":80 {"
            "    root * /srv"
            "    file_server"
            "    log"
            "    @assets {"
            "        path_regexp assets \.(css|js|png|jpg|jpeg|gif|svg|woff|woff2|eot|ttf|otf)$"
            "    }"
            '    header @assets Cache-Control "public, max-age=31536000, immutable"'
            "}"
        )
        changes_payload = {
            "field": DeploymentChange.ChangeField.BUILDER,
            "type": "UPDATE",
            "new_value": {
                "builder": Service.Builder.STATIC_DIR,
                "base_directory": "./dist",
                "custom_caddyfile": custom_caddyfile,
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
                    "not_found_page": None,
                    "is_spa": False,
                    "custom_caddyfile": custom_caddyfile,
                    "generated_caddyfile": custom_caddyfile,
                },
            },
            change.new_value,
        )

    def test_change_from_one_builder_to_another(self):
        p, service = self.create_and_deploy_git_service()

        changes_payload = {
            "field": DeploymentChange.ChangeField.BUILDER,
            "type": DeploymentChange.ChangeType.UPDATE,
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
        ).latest("created_at")
        self.assertIsNotNone(change)
        self.assertIsNotNone(change.old_value)
        jprint(change.old_value)

    async def test_deploy_service_with_staticfile_builder(self):
        p, service = await self.acreate_and_deploy_git_service(
            builder=Service.Builder.STATIC_DIR
        )
        new_deployment: Deployment = await service.alatest_production_deployment
        self.assertIsNotNone(new_deployment)
        swarm_service = self.fake_docker_client.get_deployment_service(new_deployment)
        self.assertIsNotNone(swarm_service)
        self.assertEqual(Deployment.DeploymentStatus.HEALTHY, new_deployment.status)
        self.assertTrue(new_deployment.is_current_production)

    async def test_redeploy_service_reapply_changes_correctly(self):
        p, service = await self.acreate_and_deploy_git_service()
        initial_deployment: Deployment = await service.deployments.afirst()
        jprint(initial_deployment.service_snapshot)

        changes_payload = {
            "field": DeploymentChange.ChangeField.BUILDER,
            "type": DeploymentChange.ChangeType.UPDATE,
            "new_value": {
                "builder": Service.Builder.STATIC_DIR,
                "base_directory": "./dist",
                "index_page": "./index.html",
                "not_found_page": "./404.html",
                "is_spa": True,
            },
        }
        response = await self.async_client.put(
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

        # deploy service
        response = await self.async_client.put(
            reverse(
                "zane_api:services.git.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # Redeploy
        response = self.client.put(
            reverse(
                "zane_api:services.git.redeploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                    "deployment_hash": initial_deployment.hash,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        last_deployment: Deployment = await (
            service.deployments.order_by("-queued_at")
            .select_related("is_redeploy_of")
            .afirst()
        )
        change: DeploymentChange = await last_deployment.changes.filter(
            field=DeploymentChange.ChangeField.BUILDER
        ).afirst()
        self.assertIsNotNone(change)
        self.assertEqual(DeploymentChange.ChangeType.UPDATE, change.type)

        self.assertEqual(
            {
                "builder": Service.Builder.STATIC_DIR,
                "options": {
                    "base_directory": "./dist",
                    "index_page": "./index.html",
                    "not_found_page": "./404.html",
                    "is_spa": True,
                    "custom_caddyfile": None,
                    "generated_caddyfile": generate_caddyfile_for_static_website(
                        StaticDirectoryBuilderOptions.from_dict(
                            {
                                "base_directory": "./dist",
                                "index_page": "./index.html",
                                "not_found_page": "./404.html",
                                "is_spa": True,
                                "custom_caddyfile": None,
                            }
                        )
                    ),
                },
            },
            change.old_value,
        )
        self.assertEqual(
            {
                "builder": Service.Builder.DOCKERFILE,
                "options": {
                    "dockerfile_path": "./Dockerfile",
                    "build_context_dir": "./",
                    "build_stage_target": None,
                },
            },
            change.new_value,
        )
