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
)
from ..serializers import ConfigSerializer
from ..utils import jprint


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


class DockerServiceApplyChangesViewTests(AuthAPITestCase):
    def test_apply_config_changes(
        self,
    ):
        owner = self.loginUser()
        p = Project.objects.create(slug="zaneops", owner=owner)
        service = DockerRegistryService.objects.create(slug="app", project=p)
        config_to_delete, config_to_update = Config.objects.bulk_create(
            [
                Config(
                    mount_path="/etc/caddy/hello.caddy",
                    contents=':8080 respond "here lies my life"',
                    name="to delete",
                ),
                Config(
                    mount_path="/etc/caddy/Caddyfile",
                    contents=':80 respond "hey ! I am working over here !"',
                    name="to delete",
                ),
            ]
        )
        service.configs.add(config_to_delete, config_to_update)

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
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    item_id=config_to_update.id,
                    new_value=dict(
                        mount_path="/etc/caddy/hello.caddy",
                        contents=':80 respond "here lies my life"',
                        name="hello caddyfile",
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
        self.assertEqual(2, updated_service.configs.count())

        new_volume = updated_service.configs.filter(
            mount_path="/etc/caddy/Caddyfile"
        ).first()
        self.assertIsNotNone(new_volume)

        deleted_volume = updated_service.configs.filter(id=config_to_delete.id).first()
        self.assertIsNone(deleted_volume)

        updated_config: Config = updated_service.configs.get(id=config_to_update.id)
        self.assertEqual("/etc/caddy/hello.caddy", updated_config.mount_path)
        self.assertEqual(':80 respond "here lies my life"', updated_config.contents)
        self.assertEqual("hello caddyfile", updated_config.name)
