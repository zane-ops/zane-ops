# type: ignore
from .base import AuthAPITestCase
from django.urls import reverse
from rest_framework import status
from ..models import (
    Project,
    DockerRegistryService,
    DockerDeployment,
    DockerDeploymentChange,
    Config,
    Volume,
    URL,
    PortConfiguration,
    DeploymentURL,
    DockerEnvVariable,
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
                "zane_api:services.docker.regenerate_deploy_token",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": service.slug,
                },
            ),
        )

        self.assertEqual(status.HTTP_200_OK, response.status_code)
        service.refresh_from_db()
        self.assertIsNotNone(service.deploy_token)
        self.assertEqual(20, len(service.deploy_token))

    def test_generate_deploy_token_for_service_on_creation(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="kiss-cam", owner=owner)

        create_service_payload = {
            "slug": "cache-db",
            "image": "redis:alpine",
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        created_service = DockerRegistryService.objects.get(slug="cache-db")
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
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        deployment_count = await service.deployments.acount()
        self.assertEqual(2, deployment_count)
        new_deployment: DockerDeployment = await service.alatest_production_deployment
        docker_service = self.fake_docker_client.get_deployment_service(new_deployment)
        self.assertIsNotNone(docker_service)

    async def test_webhook_deploy_service_unauthenticated(self):
        _, service = await self.acreate_and_deploy_caddy_docker_service()
        await self.async_client.alogout()

        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.webhook_deploy",
                kwargs={"deploy_token": service.deploy_token},
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        deployment_count = await service.deployments.acount()
        self.assertEqual(2, deployment_count)
        new_deployment: DockerDeployment = await service.alatest_production_deployment
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
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        service = await DockerRegistryService.objects.aget(slug=service.slug)
        deployment_count = await service.deployments.acount()
        self.assertEqual(2, deployment_count)
        new_deployment: DockerDeployment = await service.alatest_production_deployment
        docker_service = self.fake_docker_client.get_deployment_service(new_deployment)
        self.assertIsNotNone(docker_service)

        self.assertEqual("Upgrade valkey image", new_deployment.commit_message)
        self.assertEqual("valkey/valkey:7.3-alpine", service.image)


class DockerServiceRequestChangesViewTests(AuthAPITestCase):
    async def test_validate_conflicting_changes_for_single_field_types_should_merge(
        self,
    ):
        p, service = await self.acreate_and_deploy_redis_docker_service()

        changes_payload = {
            "field": DockerDeploymentChange.ChangeField.RESOURCE_LIMITS,
            "type": "UPDATE",
            "new_value": {
                "cpus": 1,
            },
        }

        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": service.slug},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        changes_payload = {
            "field": DockerDeploymentChange.ChangeField.RESOURCE_LIMITS,
            "type": "UPDATE",
            "new_value": {"cpus": 2, "memory": {"value": 500}},
        }

        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": service.slug},
            ),
            data=changes_payload,
        )

        self.assertEqual(status.HTTP_200_OK, response.status_code)

        service = await DockerRegistryService.objects.aget(slug=service.slug)
        unapplied_changes_count = await DockerDeploymentChange.objects.filter(
            service__slug=service.slug, applied=False
        ).acount()

        self.assertEqual(1, unapplied_changes_count)

        resource_limit_change: DockerDeploymentChange = (
            await DockerDeploymentChange.objects.filter(
                applied=False,
                field=DockerDeploymentChange.ChangeField.RESOURCE_LIMITS,
            ).afirst()
        )
        self.assertEqual(
            {"cpus": 2, "memory": {"value": 500, "unit": "MEGABYTES"}},
            resource_limit_change.new_value,
        )

    def test_add_config_change(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)

        create_service_payload = {
            "slug": "app",
            "image": "caddy:2.8-alpine",
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
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
            "field": DockerDeploymentChange.ChangeField.CONFIGS,
            "type": "ADD",
            "new_value": config,
        }

        response = self.client.put(
            reverse(
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        change: DockerDeploymentChange = DockerDeploymentChange.objects.filter(
            service__slug="app",
            field=DockerDeploymentChange.ChangeField.CONFIGS,
        ).first()
        self.assertIsNotNone(change)
        self.assertEqual(config, change.new_value)

    def test_add_config_change_generate_random_name_if_not_provided(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)

        create_service_payload = {
            "slug": "app",
            "image": "caddy:2.8-alpine",
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        config = {
            "contents": ':80 respond "hello from caddy"',
            "mount_path": "/etc/caddy/Caddyfile",
        }
        changes_payload = {
            "field": DockerDeploymentChange.ChangeField.CONFIGS,
            "type": "ADD",
            "new_value": config,
        }

        response = self.client.put(
            reverse(
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        change: DockerDeploymentChange = DockerDeploymentChange.objects.filter(
            service__slug="app",
            field=DockerDeploymentChange.ChangeField.CONFIGS,
        ).first()
        self.assertIsNotNone(change)
        self.assertIsNotNone(change.new_value.get("name"))

    def test_add_config_item_change_reference_previous_value(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)

        create_service_payload = {
            "slug": "app",
            "image": "caddy:2.8-alpine",
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        service = DockerRegistryService.objects.get(slug="app")
        config = Config.objects.create(
            name="caddyfile",
            contents=':80 respond "hello from caddy"',
            mount_path="/etc/caddy/Caddyfile",
        )
        service.configs.add(config)

        changes_payload = {
            "field": DockerDeploymentChange.ChangeField.CONFIGS,
            "type": "DELETE",
            "item_id": config.id,
        }

        response = self.client.put(
            reverse(
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        change: DockerDeploymentChange = DockerDeploymentChange.objects.filter(
            service__slug="app",
            field=DockerDeploymentChange.ChangeField.CONFIGS,
        ).first()
        self.assertIsNotNone(change)
        self.assertEqual(ConfigSerializer(config).data, change.old_value)

    def test_validate_config_item_change_reference_non_existent_does_not_work(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)

        create_service_payload = {
            "slug": "app",
            "image": "caddy:2.8-alpine",
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        changes_payload = {
            "field": DockerDeploymentChange.ChangeField.CONFIGS,
            "type": "DELETE",
            "item_id": "cf_1oasdkjfhb",
        }

        response = self.client.put(
            reverse(
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

        change: DockerDeploymentChange = DockerDeploymentChange.objects.filter(
            service__slug="app",
            field=DockerDeploymentChange.ChangeField.CONFIGS,
        ).first()
        self.assertIsNone(change)

    def test_validate_config_change_conflict_mount_path_with_other_config(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)

        create_service_payload = {
            "slug": "app",
            "image": "caddy:2.8-alpine",
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        service = DockerRegistryService.objects.get(slug="app")
        config = Config.objects.create(
            name="caddyfile",
            contents=':80 respond "I am the real file"',
            mount_path="/etc/caddy/Caddyfile",
        )
        service.configs.add(config)

        changes_payload = {
            "field": DockerDeploymentChange.ChangeField.CONFIGS,
            "type": DockerDeploymentChange.ChangeType.ADD,
            "new_value": dict(
                contents=':80 respond "No ! I am the real file"',
                mount_path="/etc/caddy/Caddyfile",
            ),
        }

        response = self.client.put(
            reverse(
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

        change: DockerDeploymentChange = DockerDeploymentChange.objects.filter(
            service__slug="app",
            field=DockerDeploymentChange.ChangeField.CONFIGS,
        ).first()
        self.assertIsNone(change)

    def test_validate_config_change_conflict_mount_path_with_volume(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)

        create_service_payload = {
            "slug": "app",
            "image": "caddy:2.8-alpine",
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        service = DockerRegistryService.objects.get(slug="app")
        config = Volume.objects.create(
            name="caddyfile",
            container_path="/etc/caddy/Caddyfile",
        )
        service.volumes.add(config)

        changes_payload = {
            "field": DockerDeploymentChange.ChangeField.CONFIGS,
            "type": DockerDeploymentChange.ChangeType.ADD,
            "new_value": dict(
                contents=':80 respond "This shouldn\'t work"',
                mount_path="/etc/caddy/Caddyfile",
            ),
        }

        response = self.client.put(
            reverse(
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

        change: DockerDeploymentChange = DockerDeploymentChange.objects.filter(
            service__slug="app",
            field=DockerDeploymentChange.ChangeField.CONFIGS,
        ).first()
        self.assertIsNone(change)

    def test_validate_config_change_invalid_path(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)

        create_service_payload = {
            "slug": "app",
            "image": "caddy:2.8-alpine",
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        config = {
            "contents": ':80 respond "hello from caddy"',
            "mount_path": "/etc/caddy Caddyfile",
            "name": "caddyfile",
        }
        changes_payload = {
            "field": DockerDeploymentChange.ChangeField.CONFIGS,
            "type": "ADD",
            "new_value": config,
        }

        response = self.client.put(
            reverse(
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

        change: DockerDeploymentChange = DockerDeploymentChange.objects.filter(
            service__slug="app",
            field=DockerDeploymentChange.ChangeField.CONFIGS,
        ).first()
        self.assertIsNone(change)

    def test_validate_config_do_not_prevent_updating_contents(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)

        create_service_payload = {
            "slug": "app",
            "image": "caddy:2.8-alpine",
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        service = DockerRegistryService.objects.get(slug="app")
        config = Config.objects.create(
            name="caddyfile",
            contents=':80 respond "I am the real file"',
            mount_path="/etc/caddy/Caddyfile",
        )
        service.configs.add(config)

        changes_payload = {
            "field": DockerDeploymentChange.ChangeField.CONFIGS,
            "type": DockerDeploymentChange.ChangeType.UPDATE,
            "new_value": dict(
                contents=':80 respond "No ! I am the real file"',
                mount_path="/etc/caddy/Caddyfile",
            ),
            "item_id": config.id,
        }

        response = self.client.put(
            reverse(
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        change: DockerDeploymentChange = DockerDeploymentChange.objects.filter(
            service__slug="app",
            field=DockerDeploymentChange.ChangeField.CONFIGS,
        ).first()
        self.assertIsNotNone(change)

    def test_validate_port_require_host_port(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)

        changes_payload = {
            "field": DockerDeploymentChange.ChangeField.PORTS,
            "type": DockerDeploymentChange.ChangeType.ADD,
            "new_value": {
                "forwarded": 8000,
            },
        }
        response = self.client.put(
            reverse(
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": service.slug},
            ),
            data=changes_payload,
        )

        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_validate_port_disable_exposing_port_to_http(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)

        changes_payload = {
            "field": DockerDeploymentChange.ChangeField.PORTS,
            "type": DockerDeploymentChange.ChangeType.ADD,
            "new_value": {
                "host": 80,
                "forwarded": 8000,
            },
        }
        response = self.client.put(
            reverse(
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": service.slug},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_add_url_changes_do_not_require_exposed_port(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)

        changes_payload = {
            "field": DockerDeploymentChange.ChangeField.URLS,
            "type": DockerDeploymentChange.ChangeType.ADD,
            "new_value": {
                "domain": "dcr.fredkiss.dev",
                "base_path": "/portainer",
                "associated_port": 80,
            },
        }
        response = self.client.put(
            reverse(
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": service.slug},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_add_url_changes_without_domain_generates_a_default_domain(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)

        changes_payload = {
            "field": DockerDeploymentChange.ChangeField.URLS,
            "type": DockerDeploymentChange.ChangeType.ADD,
            "new_value": {
                "base_path": "/portainer",
                "associated_port": 80,
            },
        }
        response = self.client.put(
            reverse(
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": service.slug},
            ),
            data=changes_payload,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_validate_url_changes_require_associated_port_in_request_body(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)

        changes_payload = {
            "field": DockerDeploymentChange.ChangeField.URLS,
            "type": DockerDeploymentChange.ChangeType.ADD,
            "new_value": {
                "domain": "dcr.fredkiss.dev",
                "base_path": "/portainer",
            },
        }
        response = self.client.put(
            reverse(
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": service.slug},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_validate_url_changes_prevent_passing_associated_port_in_request_body_if_redirect_to(
        self,
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)

        changes_payload = {
            "field": DockerDeploymentChange.ChangeField.URLS,
            "type": DockerDeploymentChange.ChangeType.ADD,
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
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": service.slug},
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
            "field": DockerDeploymentChange.ChangeField.URLS,
            "type": DockerDeploymentChange.ChangeType.ADD,
            "new_value": {
                "domain": first_url.domain,
                "base_path": "/portainer",
                "associated_port": 80,
            },
        }
        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": service.slug},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_add_env_string_change(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)

        create_service_payload = {
            "slug": "app",
            "image": "caddy:2.8-alpine",
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
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
                "zane_api:services.docker.request_env_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        changes: QuerySet[DockerDeploymentChange] = (
            DockerDeploymentChange.objects.filter(
                service__slug="app",
                field=DockerDeploymentChange.ChangeField.ENV_VARIABLES,
            )
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
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)

        create_service_payload = {
            "slug": "app",
            "image": "caddy:2.8-alpine",
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        # env_variable
        changes_payload = {"new_value": '"POSTGRES_USER"="posgtres"\n\ts;dlfh;\n'}

        response = self.client.put(
            reverse(
                "zane_api:services.docker.request_env_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        changes: QuerySet[DockerDeploymentChange] = (
            DockerDeploymentChange.objects.filter(
                service__slug="app",
                field=DockerDeploymentChange.ChangeField.ENV_VARIABLES,
            )
        )
        self.assertEqual(0, changes.count())

    def test_validate_env_string_change_prevent_double_env_values_with_changes(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)

        create_service_payload = {
            "slug": "app",
            "image": "caddy:2.8-alpine",
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        service = DockerRegistryService.objects.get(slug="app")

        service.add_change(
            DockerDeploymentChange(
                field=DockerDeploymentChange.ChangeField.ENV_VARIABLES,
                type=DockerDeploymentChange.ChangeType.ADD,
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
                "zane_api:services.docker.request_env_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_validate_env_string_change_prevent_double_env_values_with_service_envs(
        self,
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)

        create_service_payload = {
            "slug": "app",
            "image": "caddy:2.8-alpine",
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        service = DockerRegistryService.objects.get(slug="app")

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
                "zane_api:services.docker.request_env_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_validate_env_string_empty_string_does_nothing(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)

        create_service_payload = {
            "slug": "app",
            "image": "caddy:2.8-alpine",
        }

        response = self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        # env_variable
        changes_payload = {"new_value": ""}

        response = self.client.put(
            reverse(
                "zane_api:services.docker.request_env_changes",
                kwargs={"project_slug": p.slug, "service_slug": "app"},
            ),
            data=changes_payload,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        changes: QuerySet[DockerDeploymentChange] = (
            DockerDeploymentChange.objects.filter(
                service__slug="app",
                field=DockerDeploymentChange.ChangeField.ENV_VARIABLES,
            )
        )
        self.assertEqual(0, changes.count())


class DockerServiceRevertChangesViewTests(AuthAPITestCase):
    async def test_prevent_reverting_volume_change_if_it_result_in_invalid_state(self):
        await self.aLoginUser()
        p, service = await self.acreate_and_deploy_redis_docker_service(
            other_changes=[
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.VOLUMES,
                    type=DockerDeploymentChange.ChangeType.ADD,
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
            "field": DockerDeploymentChange.ChangeField.VOLUMES,
            "type": DockerDeploymentChange.ChangeType.UPDATE,
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
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": service.slug},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

        # now try to delete and recreate the volume
        changes_payload = {
            "field": DockerDeploymentChange.ChangeField.VOLUMES,
            "type": DockerDeploymentChange.ChangeType.DELETE,
            "item_id": new_volume.id,
        }

        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": service.slug},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        changes_payload = {
            "field": DockerDeploymentChange.ChangeField.VOLUMES,
            "type": DockerDeploymentChange.ChangeType.ADD,
            "new_value": {
                "name": "logs",
                "mode": Volume.VolumeMode.READ_ONLY,
                "container_path": "/data",
                "host_path": "/data",
            },
        }

        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": service.slug},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # Now revert the `delete` change (should not be allowed)
        change: DockerDeploymentChange = await service.changes.filter(
            applied=False,
            type=DockerDeploymentChange.ChangeType.DELETE,
            field=DockerDeploymentChange.ChangeField.VOLUMES,
        ).afirst()

        response = await self.async_client.delete(
            reverse(
                "zane_api:services.docker.cancel_deployment_changes",
                kwargs={
                    "project_slug": p.slug,
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
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.CONFIGS,
                    type=DockerDeploymentChange.ChangeType.ADD,
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
            "field": DockerDeploymentChange.ChangeField.CONFIGS,
            "type": DockerDeploymentChange.ChangeType.DELETE,
            "item_id": new_config.id,
        }

        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": service.slug},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        changes_payload = {
            "field": DockerDeploymentChange.ChangeField.CONFIGS,
            "type": DockerDeploymentChange.ChangeType.ADD,
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
                "zane_api:services.docker.request_deployment_changes",
                kwargs={"project_slug": p.slug, "service_slug": service.slug},
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # Now revert the `delete` change (should not be allowed)
        change: DockerDeploymentChange = await service.changes.filter(
            applied=False,
            type=DockerDeploymentChange.ChangeType.DELETE,
            field=DockerDeploymentChange.ChangeField.CONFIGS,
        ).afirst()

        response = await self.async_client.delete(
            reverse(
                "zane_api:services.docker.cancel_deployment_changes",
                kwargs={
                    "project_slug": p.slug,
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
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
        config_to_delete = Config.objects.create(
            mount_path="/etc/caddy/hello.caddy",
            contents=':8080 respond "here lies my life"',
            name="to delete",
        )
        service.configs.add(config_to_delete)

        DockerDeploymentChange.objects.bulk_create(
            [
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.SOURCE,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value={"image": "caddy:2.8-alpine"},
                    service=service,
                ),
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.CONFIGS,
                    type=DockerDeploymentChange.ChangeType.ADD,
                    new_value=dict(
                        mount_path="/etc/caddy/Caddyfile",
                        contents="import ./*.caddy",
                    ),
                    service=service,
                ),
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.CONFIGS,
                    type=DockerDeploymentChange.ChangeType.DELETE,
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
                    "service_slug": "app",
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        updated_service = DockerRegistryService.objects.get(slug="app")
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
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
        config_to_update = Config.objects.create(
            mount_path="/etc/caddy/Caddyfile",
            contents=':8080 respond "here lies my life"',
            name="caddyfile",
        )
        service.configs.add(config_to_update)

        DockerDeploymentChange.objects.bulk_create(
            [
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.SOURCE,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value={"image": "caddy:2.8-alpine"},
                    service=service,
                ),
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.CONFIGS,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
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
                    "service_slug": "app",
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        updated_service = DockerRegistryService.objects.get(slug="app")
        self.assertEqual(1, updated_service.configs.count())

        updated_config: Config = updated_service.configs.get(id=config_to_update.id)
        self.assertEqual(':80 respond "hello from caddy"', updated_config.contents)
        self.assertEqual(2, updated_config.version)

    def test_apply_url_changes(
        self,
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
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

        DockerDeploymentChange.objects.bulk_create(
            [
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.SOURCE,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value={"image": "caddy:2.8-alpine"},
                    service=service,
                ),
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.URLS,
                    type=DockerDeploymentChange.ChangeType.ADD,
                    new_value={
                        "domain": "web-server.fred.kiss",
                        "base_path": "/",
                        "strip_prefix": True,
                        "associated_port": 8080,
                    },
                    service=service,
                ),
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.URLS,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    item_id=url_to_update.id,
                    new_value={
                        "domain": "proxy.fredkiss.dev",
                        "base_path": "/config",
                        "strip_prefix": False,
                        "associated_port": 8081,
                    },
                    service=service,
                ),
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.URLS,
                    type=DockerDeploymentChange.ChangeType.DELETE,
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
                    "service_slug": "app",
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        updated_service = DockerRegistryService.objects.get(slug="app")
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
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)

        DockerDeploymentChange.objects.bulk_create(
            [
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.SOURCE,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value={"image": "caddy:2.8-alpine"},
                    service=service,
                ),
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.URLS,
                    type=DockerDeploymentChange.ChangeType.ADD,
                    new_value={
                        "domain": "web-server.fred.kiss",
                        "base_path": "/",
                        "strip_prefix": True,
                        "associated_port": 8080,
                    },
                    service=service,
                ),
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.URLS,
                    type=DockerDeploymentChange.ChangeType.ADD,
                    new_value={
                        "domain": "proxy.fredkiss.dev",
                        "base_path": "/config",
                        "strip_prefix": False,
                        "associated_port": 8081,
                    },
                    service=service,
                ),
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.URLS,
                    type=DockerDeploymentChange.ChangeType.ADD,
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
                    "service_slug": "app",
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        deployment: DockerDeployment = service.deployments.first()
        self.assertEqual(2, deployment.urls.count())

        ports = [
            port for port in deployment.urls.filter().values_list("port", flat=True)
        ]
        ports.sort()
        self.assertEqual([8080, 8081], ports)

    def test_apply_port_changes(
        self,
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
        port_to_delete, port_to_update = PortConfiguration.objects.bulk_create(
            [
                PortConfiguration(host=1010, forwarded=1010),
                PortConfiguration(forwarded=8000, host=8000),
            ]
        )
        service.ports.add(port_to_delete, port_to_update)

        DockerDeploymentChange.objects.bulk_create(
            [
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.SOURCE,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value={"image": "caddy:2.8-alpine"},
                    service=service,
                ),
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.PORTS,
                    type=DockerDeploymentChange.ChangeType.ADD,
                    new_value={
                        "forwarded": 9000,
                        "host": 9000,
                    },
                    service=service,
                ),
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.PORTS,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    item_id=port_to_update.id,
                    new_value={
                        "forwarded": 80,
                        "host": 8080,
                    },
                    service=service,
                ),
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.PORTS,
                    type=DockerDeploymentChange.ChangeType.DELETE,
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
                    "service_slug": "app",
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        updated_service = DockerRegistryService.objects.get(slug="app")
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
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)

        DockerDeploymentChange.objects.bulk_create(
            [
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.SOURCE,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value={"image": "caddy:2.8-alpine"},
                    service=service,
                ),
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.URLS,
                    type=DockerDeploymentChange.ChangeType.ADD,
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
                    "service_slug": "app",
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        updated_service = DockerRegistryService.objects.get(slug="app")
        new_deployment: DockerDeployment = updated_service.deployments.first()
        self.assertIsNotNone(new_deployment)
        self.assertEqual(1, new_deployment.urls.count())


class DockerServiceUpdateViewTests(AuthAPITestCase):
    async def test_update_service_with_config_remove_deleted_config(self):
        project, service = await self.acreate_and_deploy_caddy_docker_service(
            other_changes=[
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.CONFIGS,
                    type=DockerDeploymentChange.ChangeType.ADD,
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

        await DockerDeploymentChange.objects.abulk_create(
            [
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.CONFIGS,
                    type=DockerDeploymentChange.ChangeType.DELETE,
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
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.CONFIGS,
                    type=DockerDeploymentChange.ChangeType.ADD,
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

        await DockerDeploymentChange.objects.abulk_create(
            [
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.CONFIGS,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
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
