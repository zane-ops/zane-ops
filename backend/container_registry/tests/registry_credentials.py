import json
from typing import cast
from zane_api.tests.base import AuthAPITestCase
import responses
from django.urls import reverse
from zane_api.utils import jprint, find_item_in_sequence
from rest_framework import status
from ..models import ContainerRegistryCredentials
from .fixtures import (
    mock_valid_registry_no_auth,
    mock_invalid_registry,
    mock_valid_registry_with_basic_auth,
    mock_valid_registry_with_bearer_auth,
)
from zane_api.models import DeploymentChange, Project, Service, Deployment
from django.conf import settings


class TestAddRegistryCredentialsAPIView(AuthAPITestCase):
    @responses.activate()
    def test_create_simple_registry_credentials(self):
        mock_valid_registry_no_auth("https://registry.example.com")
        self.loginUser()

        body = {
            "url": "https://registry.example.com",
        }
        response = self.client.post(
            reverse("container_registry:credentials.list"), data=body
        )

        jprint(response.json())

        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        self.assertEqual(1, ContainerRegistryCredentials.objects.count())
        credential = cast(
            ContainerRegistryCredentials, ContainerRegistryCredentials.objects.first()
        )
        self.assertEqual("https://registry.example.com", credential.url)
        self.assertEqual(
            ContainerRegistryCredentials.RegistryType.GENERIC, credential.registry_type
        )
        self.assertIsNone(credential.username)
        self.assertIsNone(credential.password)

    @responses.activate()
    def test_create_registry_credentials_with_basic_auth_sucessful(self):
        mock_valid_registry_with_basic_auth(
            "https://registry.example.com",
            username="user",
            password="password",
        )
        self.loginUser()

        body = {
            "url": "https://registry.example.com",
            "username": "user",
            "password": "password",
        }
        response = self.client.post(
            reverse("container_registry:credentials.list"), data=body
        )

        jprint(response.json())

        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        self.assertEqual(1, ContainerRegistryCredentials.objects.count())
        credential = cast(
            ContainerRegistryCredentials, ContainerRegistryCredentials.objects.first()
        )
        self.assertEqual("user", credential.username)
        self.assertEqual("password", credential.password)

    @responses.activate()
    def test_create_registry_credentials_with_token_auth_sucessful(self):
        mock_valid_registry_with_bearer_auth(
            "https://registry.example.com",
            username="fredkiss3",
            password="ghp_zYz124x",
        )
        self.loginUser()

        body = {
            "url": "https://registry.example.com",
            "username": "fredkiss3",
            "password": "ghp_zYz124x",
        }
        response = self.client.post(
            reverse("container_registry:credentials.list"), data=body
        )

        jprint(response.json())

        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        self.assertEqual(1, ContainerRegistryCredentials.objects.count())
        credential = cast(
            ContainerRegistryCredentials, ContainerRegistryCredentials.objects.first()
        )
        self.assertEqual("fredkiss3", credential.username)
        self.assertEqual("ghp_zYz124x", credential.password)

    @responses.activate()
    def test_create_registry_credentials_with_token_auth_invalid_credentials(self):
        mock_valid_registry_with_bearer_auth(
            "https://registry.example.com",
            username="fredkiss3",
            password="ghp_zYz124x",
        )
        self.loginUser()

        body = {
            "url": "https://registry.example.com",
            "username": "fredkiss3",
            "password": "whatever",
        }
        response = self.client.post(
            reverse("container_registry:credentials.list"), data=body
        )

        jprint(response.json())

        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertEqual(0, ContainerRegistryCredentials.objects.count())

    @responses.activate()
    def test_create_registry_credentials_with_basic_username_and_password_requires_user_and_pass(
        self,
    ):
        mock_valid_registry_with_basic_auth(
            "https://registry.example.com",
            username="user",
            password="password",
        )
        self.loginUser()

        body = {
            "url": "https://registry.example.com",
        }
        response = self.client.post(
            reverse("container_registry:credentials.list"), data=body
        )

        jprint(response.json())

        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIsNotNone(self.get_error_from_response(response, "username"))
        self.assertIsNotNone(self.get_error_from_response(response, "password"))
        self.assertEqual(0, ContainerRegistryCredentials.objects.count())

    @responses.activate()
    def test_create_registry_credentials_with_basic_auth_wrong_credentials(
        self,
    ):
        self.loginUser()
        mock_valid_registry_with_basic_auth(
            "https://registry.example.com",
            username="user",
            password="password",
        )

        body = {
            "url": "https://registry.example.com",
            "username": "username",
            "password": "password",
        }
        response = self.client.post(
            reverse("container_registry:credentials.list"), data=body
        )

        jprint(response.json())

        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertEqual(0, ContainerRegistryCredentials.objects.count())

    @responses.activate()
    def test_create_registry_credentials_with_invalid_registry(self):
        mock_invalid_registry("https://registry.example.com")
        self.loginUser()

        body = {
            "url": "https://registry.example.com",
        }
        response = self.client.post(
            reverse("container_registry:credentials.list"), data=body
        )

        jprint(response.json())

        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        url_error = find_item_in_sequence(
            lambda e: e.get("attr") == "url", response.json().get("errors", [])
        )
        self.assertIsNotNone(url_error)


class ServiceRegistryCredentialsAPIView(AuthAPITestCase):
    @responses.activate()
    def test_create_service_with_simple_container_registry_credentials(self):
        # create simple registry
        mock_valid_registry_no_auth("https://registry.example.com")
        self.loginUser()

        body = {
            "url": "https://registry.example.com",
        }
        response = self.client.post(
            reverse("container_registry:credentials.list"), data=body
        )
        jprint(response.json())

        credential = cast(
            ContainerRegistryCredentials, ContainerRegistryCredentials.objects.first()
        )

        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        p = Project.objects.get(slug="zane-ops")

        create_service_payload = {
            "slug": "main-app",
            "image": "registry.example.com/redis:latest",
            "container_registry_credentials_id": credential.id,
        }

        response = self.client.post(
            reverse(
                "zane_api:services.docker.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        created_service = cast(Service, Service.objects.filter(slug="main-app").first())
        self.assertIsNotNone(created_service)

        self.assertEqual(1, created_service.unapplied_changes.count())
        source_change = created_service.unapplied_changes.filter(
            field=DeploymentChange.ChangeField.SOURCE
        ).get()
        new_value = cast(dict, source_change.new_value)
        self.assertIsNotNone(new_value.get("container_registry_credentials"))

    @responses.activate()
    def test_create_service_validate_registry_credentials_exists(
        self,
    ):
        self.loginUser()
        fake_id = "reg_cred_abc123xYz"

        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        p = Project.objects.get(slug="zane-ops")

        create_service_payload = {
            "slug": "main-app",
            "image": "registry.example.com/redis:latest",
            "container_registry_credentials_id": fake_id,
        }

        response = self.client.post(
            reverse(
                "zane_api:services.docker.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIsNotNone(
            self.get_error_from_response(response, "container_registry_credentials_id")
        )

    @responses.activate()
    def test_create_service_validate_image_exists_on_registry(
        self,
    ):
        self.loginUser()
        mock_valid_registry_with_basic_auth(
            "https://registry.example.com",
            username="user",
            password="password",
        )

        body = {
            "url": "https://registry.example.com",
            "username": "user",
            "password": "password",
        }
        response = self.client.post(
            reverse("container_registry:credentials.list"), data=body
        )

        jprint(response.json())
        credential = cast(
            ContainerRegistryCredentials, ContainerRegistryCredentials.objects.first()
        )

        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        p = Project.objects.get(slug="zane-ops")

        create_service_payload = {
            "slug": "main-app",
            "image": self.fake_docker_client.NONEXISTANT_PRIVATE_IMAGE,
            "container_registry_credentials_id": credential.id,
        }

        response = self.client.post(
            reverse(
                "zane_api:services.docker.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIsNotNone(self.get_error_from_response(response, "image"))

    @responses.activate()
    def test_create_service_only_accept_registry_credentials(
        self,
    ):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        p = Project.objects.get(slug="zane-ops")

        create_service_payload = {
            "slug": "main-app",
            "image": self.fake_docker_client.PRIVATE_IMAGE,
            "credentials": {
                "username": "fredkiss3",
                "password": "s3cret",
            },
        }

        response = self.client.post(
            reverse(
                "zane_api:services.docker.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=json.dumps(create_service_payload),
            content_type="application/json",
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIsNotNone(self.get_error_from_response(response, "image"))

    @responses.activate()
    def test_update_service_with_registry_credentials(
        self,
    ):
        self.loginUser()
        mock_valid_registry_with_basic_auth(
            "https://registry.example.com",
            **self.fake_docker_client.PRIVATE_IMAGE_CREDENTIALS,
        )

        body = {
            "url": "https://registry.example.com",
            **self.fake_docker_client.PRIVATE_IMAGE_CREDENTIALS,
        }
        response = self.client.post(
            reverse("container_registry:credentials.list"), data=body
        )

        jprint(response.json())
        credential = cast(
            ContainerRegistryCredentials, ContainerRegistryCredentials.objects.first()
        )

        p, service = self.create_redis_docker_service()

        changes_payload = {
            "field": DeploymentChange.ChangeField.SOURCE,
            "type": "UPDATE",
            "new_value": {
                "image": self.fake_docker_client.PRIVATE_IMAGE,
                "container_registry_credentials_id": credential.id,
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
        self.assertEqual(
            1,
            DeploymentChange.objects.filter(
                service__slug=service.slug,
                field=DeploymentChange.ChangeField.SOURCE,
            ).count(),
        )
        change = cast(
            DeploymentChange,
            DeploymentChange.objects.filter(
                service__slug=service.slug,
                field=DeploymentChange.ChangeField.SOURCE,
            ).first(),
        )
        new_value = cast(dict, change.new_value)
        self.assertIsNotNone(new_value.get("container_registry_credentials"))
        self.assertEqual(
            dict(
                id=credential.id,
                url=credential.url,
                registry_type=credential.registry_type,
                username=credential.username,
                password=credential.password,
            ),
            new_value.get("container_registry_credentials"),
        )

    @responses.activate()
    async def test_deploy_service_uses_registry_credentials(
        self,
    ):
        await self.aLoginUser()
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)

        mock_valid_registry_with_basic_auth(
            "https://registry.example.com",
            **self.fake_docker_client.PRIVATE_IMAGE_CREDENTIALS,
        )

        body = {
            "url": "https://registry.example.com",
            **self.fake_docker_client.PRIVATE_IMAGE_CREDENTIALS,
        }
        response = await self.async_client.post(
            reverse("container_registry:credentials.list"), data=body
        )

        jprint(response.json())
        credential = await ContainerRegistryCredentials.objects.aget(
            url="https://registry.example.com"
        )

        p, service = await self.acreate_redis_docker_service()

        changes_payload = {
            "field": DeploymentChange.ChangeField.SOURCE,
            "type": "UPDATE",
            "new_value": {
                "image": self.fake_docker_client.PRIVATE_IMAGE,
                "container_registry_credentials_id": credential.id,
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
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        first_deployment = cast(Deployment, await service.deployments.afirst())

        self.assertIsNotNone(first_deployment)

        self.assertEqual(Deployment.DeploymentStatus.HEALTHY, first_deployment.status)
        self.assertTrue(first_deployment.is_current_production)
