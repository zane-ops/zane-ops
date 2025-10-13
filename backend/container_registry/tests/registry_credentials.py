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
