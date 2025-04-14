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
                    "publish_directory": "./",
                    "index_page": "./index.html",
                    "not_found_page": None,
                    "is_spa": False,
                    "generated_caddyfile": generate_caddyfile_for_static_website(
                        StaticDirectoryBuilderOptions.from_dict(
                            {
                                "publish_directory": "./",
                                "index_page": "./index.html",
                            }
                        )
                    ),
                },
            },
            builder_change.new_value,
        )

        # Should create URL change
        url_change: DeploymentChange = DeploymentChange.objects.filter(
            service=created_service, field=DeploymentChange.ChangeField.URLS
        ).first()
        self.assertIsNotNone(url_change)
        self.assertEqual(DeploymentChange.ChangeType.ADD, url_change.type)
        self.assertIsNotNone(url_change.new_value.get("domain"))
        self.assertEqual("/", url_change.new_value.get("base_path"))
        self.assertEqual(True, url_change.new_value.get("strip_prefix"))
        self.assertEqual(80, url_change.new_value.get("associated_port"))

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
                "publish_directory": "./",
                "index_page": "./index.html",
                "not_found_page": None,
                "is_spa": False,
                "generated_caddyfile": generate_caddyfile_for_static_website(
                    StaticDirectoryBuilderOptions.from_dict(
                        {
                            "publish_directory": "./",
                            "index_page": "./index.html",
                        }
                    )
                ),
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
                "publish_directory": "./dist",
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
                    "publish_directory": "./dist",
                    "index_page": "./index.html",
                    "not_found_page": "./404.html",
                    "is_spa": True,
                    "generated_caddyfile": generate_caddyfile_for_static_website(
                        StaticDirectoryBuilderOptions.from_dict(
                            {
                                "publish_directory": "./dist",
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

    def test_change_from_one_builder_to_another(self):
        p, service = self.create_and_deploy_git_service()

        changes_payload = {
            "field": DeploymentChange.ChangeField.BUILDER,
            "type": DeploymentChange.ChangeType.UPDATE,
            "new_value": {
                "builder": Service.Builder.STATIC_DIR,
                "publish_directory": "./dist",
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
                "publish_directory": "./dist",
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
        response = await self.async_client.put(
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
                    "publish_directory": "./dist",
                    "index_page": "./index.html",
                    "not_found_page": "./404.html",
                    "is_spa": True,
                    "generated_caddyfile": generate_caddyfile_for_static_website(
                        StaticDirectoryBuilderOptions.from_dict(
                            {
                                "publish_directory": "./dist",
                                "index_page": "./index.html",
                                "not_found_page": "./404.html",
                                "is_spa": True,
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


class NixPacksBuilderViewTests(AuthAPITestCase):
    def test_create_service_with_nixpacks_builder(self):
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
            "builder": Service.Builder.NIXPACKS,
            "exposed_port": 3000,
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

        jprint(builder_change.new_value)
        self.assertEqual(
            Service.Builder.NIXPACKS, builder_change.new_value.get("builder")
        )
        builder_options = {
            "is_static": False,
            "build_directory": "./",
            "custom_install_command": None,
            "custom_build_command": None,
            "custom_start_command": None,
        }
        self.assertDictContainsSubset(
            builder_options, builder_change.new_value.get("options")
        )

        # Should create URL change
        url_change: DeploymentChange = DeploymentChange.objects.filter(
            service=created_service, field=DeploymentChange.ChangeField.URLS
        ).first()
        self.assertIsNotNone(url_change)
        self.assertEqual(DeploymentChange.ChangeType.ADD, url_change.type)
        self.assertIsNotNone(url_change.new_value.get("domain"))
        self.assertEqual("/", url_change.new_value.get("base_path"))
        self.assertEqual(True, url_change.new_value.get("strip_prefix"))
        self.assertEqual(3000, url_change.new_value.get("associated_port"))

        # Should create PORT env variable
        env_change: DeploymentChange = DeploymentChange.objects.filter(
            service=created_service, field=DeploymentChange.ChangeField.ENV_VARIABLES
        ).first()
        self.assertIsNotNone(env_change)
        self.assertEqual(DeploymentChange.ChangeType.ADD, env_change.type)
        self.assertEqual("PORT", env_change.new_value.get("key"))
        self.assertEqual("3000", env_change.new_value.get("value"))

    def test_create_service_with_nixpacks_and_static_builder_generates_caddyfile_and_uses_port_80(
        self,
    ):
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
            "builder": Service.Builder.NIXPACKS,
            "is_static": True,
            "exposed_port": 8080,
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

        jprint(builder_change.new_value)
        self.assertEqual(
            Service.Builder.NIXPACKS, builder_change.new_value.get("builder")
        )
        builder_options = {
            "is_static": True,
            "publish_directory": "./dist",
        }
        self.assertDictContainsSubset(
            builder_options, builder_change.new_value.get("options")
        )
        self.assertIsNotNone(
            builder_change.new_value.get("options").get("generated_caddyfile")
        )

        # Should create URL change with associated_port of 80
        url_change: DeploymentChange = DeploymentChange.objects.filter(
            service=created_service, field=DeploymentChange.ChangeField.URLS
        ).first()
        self.assertIsNotNone(url_change)
        self.assertEqual(80, url_change.new_value.get("associated_port"))

        # Should create PORT & HOST env variable
        env_changes = DeploymentChange.objects.filter(
            service=created_service,
            field=DeploymentChange.ChangeField.ENV_VARIABLES,
        )
        self.assertEqual(2, env_changes.count())

    def test_request_service_change_with_nixpacks_builder(self):
        p, service = self.create_git_service()

        changes_payload = {
            "field": DeploymentChange.ChangeField.BUILDER,
            "type": "UPDATE",
            "new_value": {
                "builder": Service.Builder.NIXPACKS,
                "build_directory": "./",
                "is_static": True,
                "is_spa": True,
                "custom_install_command": "pnpm i --frozen-lockfile",
                "custom_build_command": "pnpm run build",
                "publish_directory": "./dist",
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

        jprint(change.new_value)
        self.assertEqual(Service.Builder.NIXPACKS, change.new_value.get("builder"))
        builder_options = {
            "is_static": True,
            "is_spa": True,
            "build_directory": "./",
            "publish_directory": "./dist",
            "custom_install_command": "pnpm i --frozen-lockfile",
            "custom_build_command": "pnpm run build",
            "custom_start_command": None,
        }
        self.assertDictContainsSubset(builder_options, change.new_value.get("options"))
        self.assertIsNotNone(change.new_value.get("options").get("generated_caddyfile"))

    def test_apply_service_nixpacks_builder_change(self):
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
            "builder": Service.Builder.NIXPACKS,
            "exposed_port": 3000,
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
        self.assertEqual(Service.Builder.NIXPACKS, created_service.builder)
        self.assertIsNone(created_service.dockerfile_builder_options)
        self.assertIsNone(created_service.static_dir_builder_options)
        self.assertIsNotNone(created_service.nixpacks_builder_options)
        self.assertEqual(
            {
                "build_directory": "./",
                "custom_install_command": None,
                "custom_build_command": None,
                "custom_start_command": None,
                "is_static": False,
                "publish_directory": "./dist",
                "is_spa": False,
                "index_page": None,
                "not_found_page": "./404.html",
                "generated_caddyfile": None,
            },
            created_service.nixpacks_builder_options,
        )

    async def test_deploy_service_with_nixpacks_builder(self):
        p, service = await self.acreate_and_deploy_git_service(
            builder=Service.Builder.NIXPACKS
        )
        new_deployment: Deployment = await service.alatest_production_deployment
        self.assertIsNotNone(new_deployment)
        swarm_service = self.fake_docker_client.get_deployment_service(new_deployment)
        self.assertIsNotNone(swarm_service)
        self.assertEqual(Deployment.DeploymentStatus.HEALTHY, new_deployment.status)
        self.assertTrue(new_deployment.is_current_production)

    async def test_redeploy_git_service_reapply_old_builder_changes_correctly_with_nixpacks_builder(
        self,
    ):
        p, service = await self.acreate_and_deploy_git_service()
        initial_deployment: Deployment = await service.deployments.afirst()
        jprint(initial_deployment.service_snapshot)

        changes_payload = {
            "field": DeploymentChange.ChangeField.BUILDER,
            "type": DeploymentChange.ChangeType.UPDATE,
            "new_value": {
                "builder": Service.Builder.NIXPACKS,
                "build_directory": "./",
                "custom_start_command": "bun run db:migrate && bun run start",
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
        response = await self.async_client.put(
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
                "builder": Service.Builder.NIXPACKS,
                "options": {
                    "build_directory": "./",
                    "index_page": "./index.html",
                    "not_found_page": None,
                    "is_spa": False,
                    "is_static": False,
                    "custom_install_command": None,
                    "publish_directory": "./",
                    "custom_build_command": None,
                    "custom_start_command": "bun run db:migrate && bun run start",
                    "generated_caddyfile": None,
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

    async def test_redeploy_git_service_from_other_builder_to_nixpacks_buidler_reapply_nixpacks_builder(
        self,
    ):
        p, service = await self.acreate_and_deploy_git_service(
            builder=Service.Builder.NIXPACKS
        )
        initial_deployment: Deployment = await service.deployments.afirst()
        jprint(initial_deployment.service_snapshot)

        changes_payload = {
            "field": DeploymentChange.ChangeField.BUILDER,
            "type": DeploymentChange.ChangeType.UPDATE,
            "new_value": {
                "builder": Service.Builder.DOCKERFILE,
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
        response = await self.async_client.put(
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

        # Changes are reapplied correctly
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
                "builder": Service.Builder.NIXPACKS,
                "options": {
                    "build_directory": "./",
                    "publish_directory": "./dist",
                    "index_page": None,
                    "not_found_page": "./404.html",
                    "is_spa": False,
                    "is_static": False,
                    "custom_install_command": None,
                    "custom_build_command": None,
                    "custom_start_command": None,
                    "generated_caddyfile": None,
                },
            },
            change.new_value,
        )
        jprint(change.old_value)
        self.assertEqual(
            {
                "builder": Service.Builder.DOCKERFILE,
                "options": {
                    "dockerfile_path": "./Dockerfile",
                    "build_context_dir": "./",
                    "build_stage_target": None,
                },
            },
            change.old_value,
        )

        # Service is updated correctly
        self.assertEqual(Service.Builder.NIXPACKS, service.builder)
