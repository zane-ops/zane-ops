# type: ignore
from .base import AuthAPITestCase
from django.urls import reverse
from rest_framework import status
from ..models import (
    Project,
    Service,
    Deployment,
    DeploymentChange,
    Config,
    Volume,
    URL,
    PortConfiguration,
    DeploymentURL,
)
from ..serializers import ConfigSerializer
from ..utils import jprint
from django.db.models import QuerySet
from io import StringIO

from dotenv import dotenv_values


class DockerServiceWebhookDeployViewTests(AuthAPITestCase):
    def test_generate_deploy_token_for_service(self):
        p, service = self.create_and_deploy_caddy_docker_service()

        response = self.client.patch(
            reverse(
                "zane_api:services.regenerate_deploy_token",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )

        self.assertEqual(status.HTTP_200_OK, response.status_code)
        service.refresh_from_db()
        self.assertIsNotNone(service.deploy_token)
        self.assertEqual(20, len(service.deploy_token))

    def test_generate_deploy_token_for_service_on_creation(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "kiss-cam"},
        )
        p = Project.objects.get(slug="kiss-cam")

        create_service_payload = {
            "slug": "cache-db",
            "image": "redis:alpine",
        }

        response = self.client.post(
            reverse(
                "zane_api:services.docker.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        created_service = Service.objects.get(slug="cache-db")
        self.assertIsNotNone(created_service.deploy_token)
        self.assertEqual(20, len(created_service.deploy_token))

    async def test_webhook_deploy_service(self):
        _, service = await self.acreate_and_deploy_caddy_docker_service()

        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.webhook_deploy",
                kwargs={"deploy_token": service.deploy_token},
            ),
        )
        self.assertEqual(status.HTTP_202_ACCEPTED, response.status_code)
        deployment_count = await service.deployments.acount()
        self.assertEqual(2, deployment_count)
        new_deployment: Deployment = await service.alatest_production_deployment
        self.assertIsNotNone(new_deployment)
        self.assertEqual(
            Deployment.DeploymentTriggerMethod.WEBHOOK, new_deployment.trigger_method
        )
        docker_service = self.fake_docker_client.get_deployment_service(new_deployment)
        self.assertIsNotNone(docker_service)

    def test_webhook_deploy_initial_service_with_new_image_set_the_changes_correctly(
        self,
    ):
        _, service = self.create_redis_docker_service()

        response = self.client.put(
            reverse(
                "zane_api:services.docker.webhook_deploy",
                kwargs={"deploy_token": service.deploy_token},
            ),
            data={
                "new_image": "valkey/valkey:7.3-alpine",
            },
        )
        self.assertEqual(status.HTTP_202_ACCEPTED, response.status_code)
        self.assertEqual(1, service.deployments.count())

        first_deployment: Deployment = service.deployments.first()
        source_change: DeploymentChange = first_deployment.changes.filter(
            field=DeploymentChange.ChangeField.SOURCE
        ).first()
        self.assertIsNotNone(source_change)
        self.assertIsNone(source_change.old_value)
        self.assertEqual({"image": "valkey/valkey:7.3-alpine"}, source_change.new_value)

    async def test_webhook_deploy_service_unauthenticated(self):
        _, service = await self.acreate_and_deploy_caddy_docker_service()
        await self.async_client.alogout()

        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.webhook_deploy",
                kwargs={"deploy_token": service.deploy_token},
            ),
        )
        self.assertEqual(status.HTTP_202_ACCEPTED, response.status_code)
        deployment_count = await service.deployments.acount()
        self.assertEqual(2, deployment_count)
        new_deployment: Deployment = await service.alatest_production_deployment
        docker_service = self.fake_docker_client.get_deployment_service(new_deployment)
        self.assertIsNotNone(docker_service)

    async def test_webhook_deploy_service_with_image_and_commit_message(self):
        _, service = await self.acreate_and_deploy_redis_docker_service()

        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.webhook_deploy",
                kwargs={"deploy_token": service.deploy_token},
            ),
            data={
                "new_image": "valkey/valkey:7.3-alpine",
                "commit_message": "Upgrade valkey image",
            },
        )
        self.assertEqual(status.HTTP_202_ACCEPTED, response.status_code)
        service = await Service.objects.aget(slug=service.slug)
        deployment_count = await service.deployments.acount()
        self.assertEqual(2, deployment_count)
        new_deployment: Deployment = await service.alatest_production_deployment
        docker_service = self.fake_docker_client.get_deployment_service(new_deployment)
        self.assertIsNotNone(docker_service)

        self.assertEqual("Upgrade valkey image", new_deployment.commit_message)
        self.assertEqual("valkey/valkey:7.3-alpine", service.image)


class GitServiceWebhookDeployViewTests(AuthAPITestCase):
    async def test_webhook_deploy_git_service(self):
        _, service = await self.acreate_and_deploy_git_service()

        response = await self.async_client.put(
            reverse(
                "zane_api:services.git.webhook_deploy",
                kwargs={"deploy_token": service.deploy_token},
            ),
        )
        self.assertEqual(status.HTTP_202_ACCEPTED, response.status_code)
        deployment_count = await service.deployments.acount()
        self.assertEqual(2, deployment_count)

        new_deployment: Deployment = await service.alatest_production_deployment

        self.assertIsNotNone(new_deployment.commit_sha)
        self.assertNotEqual("HEAD", new_deployment.commit_sha)
        self.assertEqual(
            Deployment.DeploymentTriggerMethod.WEBHOOK, new_deployment.trigger_method
        )
        docker_service = self.fake_docker_client.get_deployment_service(new_deployment)
        self.assertIsNotNone(docker_service)

    def test_webhook_deploy_initial_service_with_new_commit_sha_set_the_changes_correctly(
        self,
    ):
        _, service = self.create_git_service(
            repository_url="https://github.com/zane-ops/docs"
        )

        response = self.client.put(
            reverse(
                "zane_api:services.git.webhook_deploy",
                kwargs={"deploy_token": service.deploy_token},
            ),
            data={
                "commit_sha": "abcd1236",
            },
        )
        self.assertEqual(status.HTTP_202_ACCEPTED, response.status_code)
        self.assertEqual(1, service.deployments.count())

        first_deployment: Deployment = service.deployments.first()
        source_change: DeploymentChange = first_deployment.changes.filter(
            field=DeploymentChange.ChangeField.GIT_SOURCE
        ).first()
        self.assertIsNotNone(source_change)
        self.assertIsNone(source_change.old_value)
        self.assertEqual(
            {
                "commit_sha": "abcd1236",
                "repository_url": "https://github.com/zane-ops/docs.git",
                "branch_name": "main",
            },
            source_change.new_value,
        )

    async def test_webhook_deploy_service_with_commit_sha_and_ignore_build_cache(self):
        _, service = await self.acreate_and_deploy_git_service()

        response = await self.async_client.put(
            reverse(
                "zane_api:services.git.webhook_deploy",
                kwargs={"deploy_token": service.deploy_token},
            ),
            data={
                "commit_sha": "abcd1236",
                "ignore_build_cache": True,
            },
        )
        self.assertEqual(status.HTTP_202_ACCEPTED, response.status_code)
        service = await Service.objects.aget(slug=service.slug)
        self.assertEqual(2, await service.deployments.acount())
        new_deployment: Deployment = await service.alatest_production_deployment
        self.assertIsNotNone(new_deployment)
        self.assertEqual("abcd1236", new_deployment.commit_sha)
        self.assertEqual(True, new_deployment.ignore_build_cache)


class DockerServiceRequestChangesViewTests(AuthAPITestCase):
    async def test_validate_conflicting_changes_for_single_field_types_should_merge(
        self,
    ):
        p, service = await self.acreate_and_deploy_redis_docker_service()

        changes_payload = {
            "field": DeploymentChange.ChangeField.RESOURCE_LIMITS,
            "type": "UPDATE",
            "new_value": {
                "cpus": 1,
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

        changes_payload = {
            "field": DeploymentChange.ChangeField.RESOURCE_LIMITS,
            "type": "UPDATE",
            "new_value": {"cpus": 2, "memory": {"value": 500}},
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

        service = await Service.objects.aget(slug=service.slug)
        unapplied_changes_count = await DeploymentChange.objects.filter(
            service__slug=service.slug, applied=False
        ).acount()

        self.assertEqual(1, unapplied_changes_count)

        resource_limit_change: DeploymentChange = await DeploymentChange.objects.filter(
            applied=False,
            field=DeploymentChange.ChangeField.RESOURCE_LIMITS,
        ).afirst()
        self.assertEqual(
            {"cpus": 2, "memory": {"value": 500, "unit": "MEGABYTES"}},
            resource_limit_change.new_value,
        )

    def test_add_config_change(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zaneops"},
        )
        p = Project.objects.get(slug="zaneops")

        create_service_payload = {
            "slug": "app",
            "image": "caddy:2.8-alpine",
        }

        response = self.client.post(
            reverse(
                "zane_api:services.docker.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        config = {
            "contents": ':80 respond "hello from caddy"',
            "mount_path": "/etc/caddy/Caddyfile",
            "name": "caddyfile",
            "language": "caddyfile",
        }
        changes_payload = {
            "field": DeploymentChange.ChangeField.CONFIGS,
            "type": "ADD",
            "new_value": config,
        }

        response = self.client.put(
            reverse(
                "zane_api:services.request_deployment_changes",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": "app",
                },
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        change: DeploymentChange = DeploymentChange.objects.filter(
            service__slug="app",
            field=DeploymentChange.ChangeField.CONFIGS,
        ).first()
        self.assertIsNotNone(change)
        self.assertEqual(config, change.new_value)

    def test_add_config_change_generate_random_name_if_not_provided(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zaneops"},
        )
        p = Project.objects.get(slug="zaneops")

        create_service_payload = {
            "slug": "app",
            "image": "caddy:2.8-alpine",
        }

        response = self.client.post(
            reverse(
                "zane_api:services.docker.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        config = {
            "contents": ':80 respond "hello from caddy"',
            "mount_path": "/etc/caddy/Caddyfile",
        }
        changes_payload = {
            "field": DeploymentChange.ChangeField.CONFIGS,
            "type": "ADD",
            "new_value": config,
        }

        response = self.client.put(
            reverse(
                "zane_api:services.request_deployment_changes",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": "app",
                },
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        change: DeploymentChange = DeploymentChange.objects.filter(
            service__slug="app",
            field=DeploymentChange.ChangeField.CONFIGS,
        ).first()
        self.assertIsNotNone(change)
        self.assertIsNotNone(change.new_value.get("name"))

    def test_add_config_item_change_reference_previous_value(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zaneops"},
        )
        p = Project.objects.get(slug="zaneops")

        create_service_payload = {
            "slug": "app",
            "image": "caddy:2.8-alpine",
        }

        response = self.client.post(
            reverse(
                "zane_api:services.docker.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        service = Service.objects.get(slug="app")
        config = Config.objects.create(
            name="caddyfile",
            contents=':80 respond "hello from caddy"',
            mount_path="/etc/caddy/Caddyfile",
        )
        service.configs.add(config)

        changes_payload = {
            "field": DeploymentChange.ChangeField.CONFIGS,
            "type": "DELETE",
            "item_id": config.id,
        }

        response = self.client.put(
            reverse(
                "zane_api:services.request_deployment_changes",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": "app",
                },
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        change: DeploymentChange = DeploymentChange.objects.filter(
            service__slug="app",
            field=DeploymentChange.ChangeField.CONFIGS,
        ).first()
        self.assertIsNotNone(change)
        self.assertEqual(ConfigSerializer(config).data, change.old_value)

    def test_validate_config_item_change_reference_non_existent_does_not_work(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zaneops"},
        )
        p = Project.objects.get(slug="zaneops")

        create_service_payload = {
            "slug": "app",
            "image": "caddy:2.8-alpine",
        }

        response = self.client.post(
            reverse(
                "zane_api:services.docker.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        changes_payload = {
            "field": DeploymentChange.ChangeField.CONFIGS,
            "type": "DELETE",
            "item_id": "cf_1oasdkjfhb",
        }

        response = self.client.put(
            reverse(
                "zane_api:services.request_deployment_changes",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": "app",
                },
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

        change: DeploymentChange = DeploymentChange.objects.filter(
            service__slug="app",
            field=DeploymentChange.ChangeField.CONFIGS,
        ).first()
        self.assertIsNone(change)

    def test_validate_config_change_conflict_mount_path_with_other_config(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zaneops"},
        )
        p = Project.objects.get(slug="zaneops")

        create_service_payload = {
            "slug": "app",
            "image": "caddy:2.8-alpine",
        }

        response = self.client.post(
            reverse(
                "zane_api:services.docker.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        service = Service.objects.get(slug="app")
        config = Config.objects.create(
            name="caddyfile",
            contents=':80 respond "I am the real file"',
            mount_path="/etc/caddy/Caddyfile",
        )
        service.configs.add(config)

        changes_payload = {
            "field": DeploymentChange.ChangeField.CONFIGS,
            "type": DeploymentChange.ChangeType.ADD,
            "new_value": dict(
                contents=':80 respond "No ! I am the real file"',
                mount_path="/etc/caddy/Caddyfile",
            ),
        }

        response = self.client.put(
            reverse(
                "zane_api:services.request_deployment_changes",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": "app",
                },
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

        change: DeploymentChange = DeploymentChange.objects.filter(
            service__slug="app",
            field=DeploymentChange.ChangeField.CONFIGS,
        ).first()
        self.assertIsNone(change)

    def test_validate_config_change_conflict_mount_path_with_volume(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zaneops"},
        )
        p = Project.objects.get(slug="zaneops")

        create_service_payload = {
            "slug": "app",
            "image": "caddy:2.8-alpine",
        }

        response = self.client.post(
            reverse(
                "zane_api:services.docker.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        service = Service.objects.get(slug="app")
        config = Volume.objects.create(
            name="caddyfile",
            container_path="/etc/caddy/Caddyfile",
        )
        service.volumes.add(config)

        changes_payload = {
            "field": DeploymentChange.ChangeField.CONFIGS,
            "type": DeploymentChange.ChangeType.ADD,
            "new_value": dict(
                contents=':80 respond "This shouldn\'t work"',
                mount_path="/etc/caddy/Caddyfile",
            ),
        }

        response = self.client.put(
            reverse(
                "zane_api:services.request_deployment_changes",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": "app",
                },
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

        change: DeploymentChange = DeploymentChange.objects.filter(
            service__slug="app",
            field=DeploymentChange.ChangeField.CONFIGS,
        ).first()
        self.assertIsNone(change)

    def test_validate_config_change_invalid_path(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zaneops"},
        )
        p = Project.objects.get(slug="zaneops")

        create_service_payload = {
            "slug": "app",
            "image": "caddy:2.8-alpine",
        }

        response = self.client.post(
            reverse(
                "zane_api:services.docker.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        config = {
            "contents": ':80 respond "hello from caddy"',
            "mount_path": "/etc/caddy Caddyfile",
            "name": "caddyfile",
        }
        changes_payload = {
            "field": DeploymentChange.ChangeField.CONFIGS,
            "type": "ADD",
            "new_value": config,
        }

        response = self.client.put(
            reverse(
                "zane_api:services.request_deployment_changes",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": "app",
                },
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

        change: DeploymentChange = DeploymentChange.objects.filter(
            service__slug="app",
            field=DeploymentChange.ChangeField.CONFIGS,
        ).first()
        self.assertIsNone(change)

    def test_validate_config_do_not_prevent_updating_contents(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zaneops"},
        )
        p = Project.objects.get(slug="zaneops")

        create_service_payload = {
            "slug": "app",
            "image": "caddy:2.8-alpine",
        }

        response = self.client.post(
            reverse(
                "zane_api:services.docker.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        service = Service.objects.get(slug="app")
        config = Config.objects.create(
            name="caddyfile",
            contents=':80 respond "I am the real file"',
            mount_path="/etc/caddy/Caddyfile",
        )
        service.configs.add(config)

        changes_payload = {
            "field": DeploymentChange.ChangeField.CONFIGS,
            "type": DeploymentChange.ChangeType.UPDATE,
            "new_value": dict(
                contents=':80 respond "No ! I am the real file"',
                mount_path="/etc/caddy/Caddyfile",
            ),
            "item_id": config.id,
        }

        response = self.client.put(
            reverse(
                "zane_api:services.request_deployment_changes",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": "app",
                },
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        change: DeploymentChange = DeploymentChange.objects.filter(
            service__slug="app",
            field=DeploymentChange.ChangeField.CONFIGS,
        ).first()
        self.assertIsNotNone(change)

    def test_validate_port_require_host_port(self):
        p, service = self.create_and_deploy_caddy_docker_service()

        changes_payload = {
            "field": DeploymentChange.ChangeField.PORTS,
            "type": DeploymentChange.ChangeType.ADD,
            "new_value": {
                "forwarded": 8000,
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

        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_validate_port_disable_exposing_port_to_http(self):
        p, service = self.create_and_deploy_caddy_docker_service()

        changes_payload = {
            "field": DeploymentChange.ChangeField.PORTS,
            "type": DeploymentChange.ChangeType.ADD,
            "new_value": {
                "host": 80,
                "forwarded": 8000,
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
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_add_url_changes_do_not_require_exposed_port(self):
        p, service = self.create_and_deploy_caddy_docker_service()

        changes_payload = {
            "field": DeploymentChange.ChangeField.URLS,
            "type": DeploymentChange.ChangeType.ADD,
            "new_value": {
                "domain": "dcr.fredkiss.dev",
                "base_path": "/portainer",
                "associated_port": 80,
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

    def test_add_url_changes_without_domain_generates_a_default_domain(self):
        p, service = self.create_and_deploy_caddy_docker_service()

        changes_payload = {
            "field": DeploymentChange.ChangeField.URLS,
            "type": DeploymentChange.ChangeType.ADD,
            "new_value": {
                "base_path": "/portainer",
                "associated_port": 80,
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
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_validate_url_changes_require_associated_port_in_request_body(self):
        p, service = self.create_and_deploy_caddy_docker_service()

        changes_payload = {
            "field": DeploymentChange.ChangeField.URLS,
            "type": DeploymentChange.ChangeType.ADD,
            "new_value": {
                "domain": "dcr.fredkiss.dev",
                "base_path": "/portainer",
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
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_validate_url_changes_prevent_passing_associated_port_in_request_body_if_redirect_to(
        self,
    ):
        p, service = self.create_and_deploy_caddy_docker_service()

        changes_payload = {
            "field": DeploymentChange.ChangeField.URLS,
            "type": DeploymentChange.ChangeType.ADD,
            "new_value": {
                "domain": "dcr.fredkiss.dev",
                "base_path": "/portainer",
                "associated_port": 8000,
                "redirect_to": {
                    "url": "https://hello.fkss.me",
                },
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
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    async def test_validate_url_cannot_use_deployment_domain(self):
        p, service = await self.acreate_and_deploy_caddy_docker_service()

        latest_deployment = await service.alatest_production_deployment
        self.assertIsNotNone(latest_deployment)

        first_url: DeploymentURL = await latest_deployment.urls.afirst()  # type: ignore
        changes_payload = {
            "field": DeploymentChange.ChangeField.URLS,
            "type": DeploymentChange.ChangeType.ADD,
            "new_value": {
                "domain": first_url.domain,
                "base_path": "/portainer",
                "associated_port": 80,
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
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_add_env_string_change(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zaneops"},
        )
        p = Project.objects.get(slug="zaneops")

        create_service_payload = {
            "slug": "app",
            "image": "caddy:2.8-alpine",
        }

        response = self.client.post(
            reverse(
                "zane_api:services.docker.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        # env_variable
        changes_payload = {
            "new_value": (
                'POSTGRES_USER="posgtres"\n'
                + 'POSTGRES_DB="zaneops"\n'
                + "POSTGRES_PASSWORD=password\n"
            )
        }

        response = self.client.put(
            reverse(
                "zane_api:services.request_env_changes",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": "app",
                },
            ),
            data=changes_payload,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        changes: QuerySet[DeploymentChange] = DeploymentChange.objects.filter(
            service__slug="app",
            field=DeploymentChange.ChangeField.ENV_VARIABLES,
        )
        self.assertEqual(3, changes.count())
        env_variables = {
            ch.new_value.get("key"): ch.new_value.get("value") for ch in changes
        }
        values = dotenv_values(stream=StringIO(changes_payload["new_value"]))
        jprint(values)
        self.assertEqual(
            values,
            env_variables,
        )

    def test_validate_env_string_change_refuse_invalid_value(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zaneops"},
        )
        p = Project.objects.get(slug="zaneops")

        create_service_payload = {
            "slug": "app",
            "image": "caddy:2.8-alpine",
        }

        response = self.client.post(
            reverse(
                "zane_api:services.docker.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        # env_variable
        changes_payload = {"new_value": '"POSTGRES_USER"="posgtres"\n\ts;dlfh;\n'}

        response = self.client.put(
            reverse(
                "zane_api:services.request_env_changes",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": "app",
                },
            ),
            data=changes_payload,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        changes: QuerySet[DeploymentChange] = DeploymentChange.objects.filter(
            service__slug="app",
            field=DeploymentChange.ChangeField.ENV_VARIABLES,
        )
        self.assertEqual(0, changes.count())

    def test_validate_env_string_change_prevent_double_env_values_with_changes(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zaneops"},
        )
        p = Project.objects.get(
            slug="zaneops",
        )

        create_service_payload = {
            "slug": "app",
            "image": "caddy:2.8-alpine",
        }

        response = self.client.post(
            reverse(
                "zane_api:services.docker.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        service = Service.objects.get(slug="app")

        service.add_change(
            DeploymentChange(
                field=DeploymentChange.ChangeField.ENV_VARIABLES,
                type=DeploymentChange.ChangeType.ADD,
                new_value={"key": "POSTGRES_USER", "value": "zane"},
            )
        )

        # env_variable
        changes_payload = {
            "new_value": (
                'POSTGRES_USER="posgtres"\n'
                + 'POSTGRES_DB="zaneops"\n'
                + "POSTGRES_PASSWORD=password\n"
            )
        }

        response = self.client.put(
            reverse(
                "zane_api:services.request_env_changes",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": "app",
                },
            ),
            data=changes_payload,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_validate_env_string_change_prevent_double_env_values_with_service_envs(
        self,
    ):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zaneops"},
        )
        p = Project.objects.get(slug="zaneops")

        create_service_payload = {
            "slug": "app",
            "image": "caddy:2.8-alpine",
        }

        response = self.client.post(
            reverse(
                "zane_api:services.docker.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        service = Service.objects.get(slug="app")

        service.env_variables.create(key="POSTGRES_DB", value="zane-db")

        # env_variable
        changes_payload = {
            "new_value": (
                'POSTGRES_USER="posgtres"\n'
                + 'POSTGRES_DB="zaneops"\n'
                + "POSTGRES_PASSWORD=password\n"
            )
        }

        response = self.client.put(
            reverse(
                "zane_api:services.request_env_changes",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": "app",
                },
            ),
            data=changes_payload,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_validate_env_string_empty_string_does_nothing(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zaneops"},
        )
        p = Project.objects.get(slug="zaneops")

        create_service_payload = {
            "slug": "app",
            "image": "caddy:2.8-alpine",
        }

        response = self.client.post(
            reverse(
                "zane_api:services.docker.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        # env_variable
        changes_payload = {"new_value": ""}

        response = self.client.put(
            reverse(
                "zane_api:services.request_env_changes",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": "app",
                },
            ),
            data=changes_payload,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        changes: QuerySet[DeploymentChange] = DeploymentChange.objects.filter(
            service__slug="app",
            field=DeploymentChange.ChangeField.ENV_VARIABLES,
        )
        self.assertEqual(0, changes.count())

    def test_validate_url_can_update_subdomain_if_wildcard_exists_and_is_attached_to_same_service(
        self,
    ):
        p, service = self.create_caddy_docker_service()
        new_url = URL.objects.create(domain="*.gh.fredkiss.dev", associated_port=80)
        service.urls.add(new_url)

        changes_payload = {
            "field": "urls",
            "type": "UPDATE",
            "item_id": new_url.id,
            "new_value": {
                "domain": "*.gh.fredkiss.dev",
                "associated_port": 3000,
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
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_validate_url_can_use_wildcard_subdomain_if_wildcard_exists_and_is_attached_to_another_service_on_another_path(
        self,
    ):
        p, service = self.create_caddy_docker_service()
        new_url = URL.objects.create(domain="*.gh.fredkiss.dev", associated_port=80)
        service.urls.add(new_url)

        changes_payload = {
            "field": "urls",
            "type": "ADD",
            "new_value": {
                "domain": "*.gh.fredkiss.dev",
                "base_path": "/api",
                "associated_port": 3000,
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
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_validate_url_cannot_add_subdomain_even_if_wildcard_exists_and_is_attached_to_same_service(
        self,
    ):
        p, service = self.create_caddy_docker_service()
        new_url = URL.objects.create(domain="*.gh.fredkiss.dev", associated_port=80)
        service.urls.add(new_url)

        changes_payload = {
            "field": "urls",
            "type": "ADD",
            "new_value": {
                "domain": "abc.gh.fredkiss.dev",
                "associated_port": 3000,
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
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)


class DockerServiceRevertChangesViewTests(AuthAPITestCase):
    async def test_prevent_reverting_volume_change_if_it_result_in_invalid_state(self):
        await self.aLoginUser()
        p, service = await self.acreate_and_deploy_redis_docker_service(
            other_changes=[
                DeploymentChange(
                    field=DeploymentChange.ChangeField.VOLUMES,
                    type=DeploymentChange.ChangeType.ADD,
                    new_value={
                        "container_path": "/data",
                        "mode": Volume.VolumeMode.READ_WRITE,
                        "name": "data",
                    },
                ),
            ]
        )

        new_deployment = await service.alatest_production_deployment
        self.assertIsNotNone(new_deployment)
        docker_service = self.fake_docker_client.get_deployment_service(new_deployment)

        self.assertIsNotNone(docker_service)
        self.assertEqual(1, len(self.fake_docker_client.volume_map))
        self.assertEqual(1, len(docker_service.attached_volumes))

        new_volume = await service.volumes.afirst()

        # what we want to do
        changes_payload = {
            "field": DeploymentChange.ChangeField.VOLUMES,
            "type": DeploymentChange.ChangeType.UPDATE,
            "item_id": new_volume.id,
            "new_value": {
                "name": "logs",
                "mode": Volume.VolumeMode.READ_ONLY,
                "container_path": "/data",
                "host_path": "/data",
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
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

        # now try to delete and recreate the volume
        changes_payload = {
            "field": DeploymentChange.ChangeField.VOLUMES,
            "type": DeploymentChange.ChangeType.DELETE,
            "item_id": new_volume.id,
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

        changes_payload = {
            "field": DeploymentChange.ChangeField.VOLUMES,
            "type": DeploymentChange.ChangeType.ADD,
            "new_value": {
                "name": "logs",
                "mode": Volume.VolumeMode.READ_ONLY,
                "container_path": "/data",
                "host_path": "/data",
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

        # Now revert the `delete` change (should not be allowed)
        change: DeploymentChange = await service.changes.filter(
            applied=False,
            type=DeploymentChange.ChangeType.DELETE,
            field=DeploymentChange.ChangeField.VOLUMES,
        ).afirst()

        response = await self.async_client.delete(
            reverse(
                "zane_api:services.cancel_service_changes",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                    "change_id": change.id,
                },
            ),
        )
        self.assertEqual(status.HTTP_409_CONFLICT, response.status_code)

    async def test_prevent_reverting_config_change_if_it_result_in_invalid_state(self):
        await self.aLoginUser()
        p, service = await self.acreate_and_deploy_caddy_docker_service(
            other_changes=[
                DeploymentChange(
                    field=DeploymentChange.ChangeField.CONFIGS,
                    type=DeploymentChange.ChangeType.ADD,
                    new_value={
                        "contents": ':80 respond "hello from caddy"',
                        "mount_path": "/etc/caddy/Caddyfile",
                        "name": "caddyfile",
                        "language": "caddyfile",
                    },
                ),
            ]
        )

        new_config: Config = await service.configs.afirst()

        # try to delete and recreate the config file
        changes_payload = {
            "field": DeploymentChange.ChangeField.CONFIGS,
            "type": DeploymentChange.ChangeType.DELETE,
            "item_id": new_config.id,
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

        changes_payload = {
            "field": DeploymentChange.ChangeField.CONFIGS,
            "type": DeploymentChange.ChangeType.ADD,
            "new_value": {
                "name": "caddyfile",
                "language": "caddyfile",
                "contents": """
                :80 {
                    respond "hello from caddy"
                }
                """,
                "mount_path": "/etc/caddy/Caddyfile",
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

        # Now revert the `delete` change (should not be allowed)
        change: DeploymentChange = await service.changes.filter(
            applied=False,
            type=DeploymentChange.ChangeType.DELETE,
            field=DeploymentChange.ChangeField.CONFIGS,
        ).afirst()

        response = await self.async_client.delete(
            reverse(
                "zane_api:services.cancel_service_changes",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                    "change_id": change.id,
                },
            ),
        )
        self.assertEqual(status.HTTP_409_CONFLICT, response.status_code)


class DockerServiceApplyChangesViewTests(AuthAPITestCase):
    def test_apply_config_changes(
        self,
    ):
        p, service = self.create_and_deploy_caddy_docker_service()
        config_to_delete = Config.objects.create(
            mount_path="/etc/caddy/hello.caddy",
            contents=':8080 respond "here lies my life"',
            name="to delete",
        )
        service.configs.add(config_to_delete)

        DeploymentChange.objects.bulk_create(
            [
                DeploymentChange(
                    field=DeploymentChange.ChangeField.SOURCE,
                    type=DeploymentChange.ChangeType.UPDATE,
                    new_value={"image": "caddy:2.8-alpine"},
                    service=service,
                ),
                DeploymentChange(
                    field=DeploymentChange.ChangeField.CONFIGS,
                    type=DeploymentChange.ChangeType.ADD,
                    new_value=dict(
                        mount_path="/etc/caddy/Caddyfile",
                        contents="import ./*.caddy",
                    ),
                    service=service,
                ),
                DeploymentChange(
                    field=DeploymentChange.ChangeField.CONFIGS,
                    type=DeploymentChange.ChangeType.DELETE,
                    item_id=config_to_delete.id,
                    service=service,
                ),
            ]
        )

        response = self.client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        updated_service = Service.objects.get(slug=service.slug)
        self.assertEqual(1, updated_service.configs.count())

        new_config = updated_service.configs.filter(
            mount_path="/etc/caddy/Caddyfile"
        ).first()
        self.assertIsNotNone(new_config)

        deleted_config = updated_service.configs.filter(id=config_to_delete.id).first()
        self.assertIsNone(deleted_config)

    def test_updating_config_content_increments_version(
        self,
    ):
        p, service = self.create_and_deploy_caddy_docker_service()
        config_to_update = Config.objects.create(
            mount_path="/etc/caddy/Caddyfile",
            contents=':8080 respond "here lies my life"',
            name="caddyfile",
        )
        service.configs.add(config_to_update)

        DeploymentChange.objects.bulk_create(
            [
                DeploymentChange(
                    field=DeploymentChange.ChangeField.SOURCE,
                    type=DeploymentChange.ChangeType.UPDATE,
                    new_value={"image": "caddy:2.8-alpine"},
                    service=service,
                ),
                DeploymentChange(
                    field=DeploymentChange.ChangeField.CONFIGS,
                    type=DeploymentChange.ChangeType.UPDATE,
                    item_id=config_to_update.id,
                    new_value=dict(
                        mount_path="/etc/caddy/Caddyfile",
                        contents=':80 respond "hello from caddy"',
                        name="caddyfile",
                    ),
                    service=service,
                ),
            ]
        )

        response = self.client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        updated_service = Service.objects.get(slug=service.slug)
        self.assertEqual(1, updated_service.configs.count())

        updated_config: Config = updated_service.configs.get(id=config_to_update.id)
        self.assertEqual(':80 respond "hello from caddy"', updated_config.contents)
        self.assertEqual(2, updated_config.version)

    def test_apply_url_changes(
        self,
    ):
        p, service = self.create_caddy_docker_service()
        url_to_delete, url_to_update = URL.objects.bulk_create(
            [
                URL(base_path="/unused", domain="old-domain.com", associated_port=8080),
                URL(
                    base_path="/",
                    domain="caddy-test.fredkiss.dev",
                    associated_port=8080,
                ),
            ]
        )
        service.urls.add(url_to_delete, url_to_update)

        DeploymentChange.objects.bulk_create(
            [
                DeploymentChange(
                    field=DeploymentChange.ChangeField.SOURCE,
                    type=DeploymentChange.ChangeType.UPDATE,
                    new_value={"image": "caddy:2.8-alpine"},
                    service=service,
                ),
                DeploymentChange(
                    field=DeploymentChange.ChangeField.URLS,
                    type=DeploymentChange.ChangeType.ADD,
                    new_value={
                        "domain": "web-server.fred.kiss",
                        "base_path": "/",
                        "strip_prefix": True,
                        "associated_port": 8080,
                    },
                    service=service,
                ),
                DeploymentChange(
                    field=DeploymentChange.ChangeField.URLS,
                    type=DeploymentChange.ChangeType.UPDATE,
                    item_id=url_to_update.id,
                    new_value={
                        "domain": "proxy.fredkiss.dev",
                        "base_path": "/config",
                        "strip_prefix": False,
                        "associated_port": 8081,
                    },
                    service=service,
                ),
                DeploymentChange(
                    field=DeploymentChange.ChangeField.URLS,
                    type=DeploymentChange.ChangeType.DELETE,
                    item_id=url_to_delete.id,
                    service=service,
                ),
            ]
        )

        response = self.client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        updated_service = Service.objects.get(slug=service.slug)
        self.assertEqual(2, updated_service.urls.count())

        new_url = updated_service.urls.filter(domain="web-server.fred.kiss").first()
        self.assertIsNotNone(new_url)

        deleted_url = updated_service.urls.filter(id=url_to_delete.id).first()
        self.assertIsNone(deleted_url)

        updated_url = updated_service.urls.get(id=url_to_update.id)
        self.assertEqual("proxy.fredkiss.dev", updated_url.domain)
        self.assertEqual("/config", updated_url.base_path)
        self.assertEqual(8081, updated_url.associated_port)
        self.assertEqual(False, updated_url.strip_prefix)

    def test_apply_urls_changes_create_as_many_deployment_urls_as_there_ports(self):
        p, service = self.create_caddy_docker_service()

        DeploymentChange.objects.bulk_create(
            [
                DeploymentChange(
                    field=DeploymentChange.ChangeField.SOURCE,
                    type=DeploymentChange.ChangeType.UPDATE,
                    new_value={"image": "caddy:2.8-alpine"},
                    service=service,
                ),
                DeploymentChange(
                    field=DeploymentChange.ChangeField.URLS,
                    type=DeploymentChange.ChangeType.ADD,
                    new_value={
                        "domain": "web-server.fred.kiss",
                        "base_path": "/",
                        "strip_prefix": True,
                        "associated_port": 8080,
                    },
                    service=service,
                ),
                DeploymentChange(
                    field=DeploymentChange.ChangeField.URLS,
                    type=DeploymentChange.ChangeType.ADD,
                    new_value={
                        "domain": "proxy.fredkiss.dev",
                        "base_path": "/config",
                        "strip_prefix": False,
                        "associated_port": 8081,
                    },
                    service=service,
                ),
                DeploymentChange(
                    field=DeploymentChange.ChangeField.URLS,
                    type=DeploymentChange.ChangeType.ADD,
                    new_value={
                        "domain": "proxy2.fredkiss.dev",
                        "base_path": "/config",
                        "strip_prefix": False,
                        "associated_port": 8081,
                    },
                    service=service,
                ),
            ]
        )

        response = self.client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        deployment: Deployment = service.deployments.first()
        self.assertEqual(2, deployment.urls.count())

        ports = [
            port for port in deployment.urls.filter().values_list("port", flat=True)
        ]
        ports.sort()
        self.assertEqual([8080, 8081], ports)

    def test_apply_port_changes(
        self,
    ):
        p, service = self.create_and_deploy_caddy_docker_service()
        port_to_delete, port_to_update = PortConfiguration.objects.bulk_create(
            [
                PortConfiguration(host=1010, forwarded=1010),
                PortConfiguration(forwarded=8000, host=8000),
            ]
        )
        service.ports.add(port_to_delete, port_to_update)

        DeploymentChange.objects.bulk_create(
            [
                DeploymentChange(
                    field=DeploymentChange.ChangeField.SOURCE,
                    type=DeploymentChange.ChangeType.UPDATE,
                    new_value={"image": "caddy:2.8-alpine"},
                    service=service,
                ),
                DeploymentChange(
                    field=DeploymentChange.ChangeField.PORTS,
                    type=DeploymentChange.ChangeType.ADD,
                    new_value={
                        "forwarded": 9000,
                        "host": 9000,
                    },
                    service=service,
                ),
                DeploymentChange(
                    field=DeploymentChange.ChangeField.PORTS,
                    type=DeploymentChange.ChangeType.UPDATE,
                    item_id=port_to_update.id,
                    new_value={
                        "forwarded": 80,
                        "host": 8080,
                    },
                    service=service,
                ),
                DeploymentChange(
                    field=DeploymentChange.ChangeField.PORTS,
                    type=DeploymentChange.ChangeType.DELETE,
                    item_id=port_to_delete.id,
                    service=service,
                ),
            ]
        )

        response = self.client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        updated_service = Service.objects.get(slug=service.slug)
        self.assertEqual(2, updated_service.ports.count())

        new_port = updated_service.ports.filter(host=9000).first()
        self.assertIsNotNone(new_port)

        deleted_port = updated_service.ports.filter(id=port_to_delete.id).first()
        self.assertIsNone(deleted_port)

        updated_port = updated_service.ports.get(id=port_to_update.id)
        self.assertEqual(8080, updated_port.host)
        self.assertEqual(80, updated_port.forwarded)

    def test_apply_changes_creates_a_deployment_with_url_if_service_has_url_provided(
        self,
    ):
        p, service = self.create_caddy_docker_service()

        DeploymentChange.objects.bulk_create(
            [
                DeploymentChange(
                    field=DeploymentChange.ChangeField.SOURCE,
                    type=DeploymentChange.ChangeType.UPDATE,
                    new_value={"image": "caddy:2.8-alpine"},
                    service=service,
                ),
                DeploymentChange(
                    field=DeploymentChange.ChangeField.URLS,
                    type=DeploymentChange.ChangeType.ADD,
                    new_value={
                        "domain": "hello.local",
                        "base_path": "/",
                        "associated_port": 80,
                        "strip_prefix": False,
                    },
                    service=service,
                ),
            ]
        )

        response = self.client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        updated_service = Service.objects.get(slug=service.slug)
        new_deployment: Deployment = updated_service.deployments.first()
        self.assertIsNotNone(new_deployment)
        self.assertEqual(1, new_deployment.urls.count())


class DockerServiceUpdateViewTests(AuthAPITestCase):
    async def test_update_service_with_config_remove_deleted_config(self):
        project, service = await self.acreate_and_deploy_caddy_docker_service(
            other_changes=[
                DeploymentChange(
                    field=DeploymentChange.ChangeField.CONFIGS,
                    type=DeploymentChange.ChangeType.ADD,
                    new_value={
                        "contents": ':80 respond "hello from caddy"',
                        "mount_path": "/etc/caddy/Caddyfile",
                        "name": "caddyfile",
                        "language": "caddyfile",
                    },
                ),
            ]
        )
        config_to_delete: Config = await service.configs.afirst()

        await DeploymentChange.objects.abulk_create(
            [
                DeploymentChange(
                    field=DeploymentChange.ChangeField.CONFIGS,
                    type=DeploymentChange.ChangeType.DELETE,
                    service=service,
                    item_id=config_to_delete.id,
                ),
            ]
        )
        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(2, await service.deployments.acount())
        self.assertEqual(0, len(self.fake_docker_client.config_map))

    async def test_update_service_config_contents_recreate_config(
        self,
    ):
        project, service = await self.acreate_and_deploy_caddy_docker_service(
            other_changes=[
                DeploymentChange(
                    field=DeploymentChange.ChangeField.CONFIGS,
                    type=DeploymentChange.ChangeType.ADD,
                    new_value={
                        "contents": ':80 respond "hello from caddy"',
                        "mount_path": "/etc/caddy/Caddyfile",
                        "name": "caddyfile",
                        "language": "caddyfile",
                    },
                ),
            ]
        )
        config_to_update: Config = await service.configs.afirst()

        await DeploymentChange.objects.abulk_create(
            [
                DeploymentChange(
                    field=DeploymentChange.ChangeField.CONFIGS,
                    type=DeploymentChange.ChangeType.UPDATE,
                    service=service,
                    item_id=config_to_update.id,
                    new_value={
                        "contents": ':80 respond "hello from caddy2"',
                        "mount_path": "/etc/caddy/Caddyfile",
                        "name": "caddyfile",
                        "language": "caddyfile",
                    },
                ),
            ]
        )
        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(2, await service.deployments.acount())
        self.assertEqual(1, len(self.fake_docker_client.config_map))

        new_deployment = await service.alatest_production_deployment
        self.assertIsNotNone(new_deployment)
        docker_service = self.fake_docker_client.get_deployment_service(new_deployment)

        self.assertIsNone(docker_service.get_attached_config(config_to_update))

        updated_config: Config = await service.configs.afirst()
        self.assertIsNotNone(docker_service.get_attached_config(updated_config))
