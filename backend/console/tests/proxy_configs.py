# type: ignore
import requests
from django.conf import settings
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status

from zane_api.tests.base import AuthAPITestCase
from zane_api.utils import jprint

from ..models import CustomProxyConfig

VALID_CADDYFILE = """
http://custom.zaneops.local {
    respond "hello from a custom config"
}
"""

OTHER_VALID_CADDYFILE = """
http://other.zaneops.local {
    respond "hello from another custom config" 201
}
"""

INVALID_CADDYFILE = """
http://custom.zaneops.local {
    respond_with_something_that_does_not_exist "oops"
"""


class CustomProxyConfigViewTests(AuthAPITestCase):
    def get_caddy_route(self, config_id: str):
        return requests.get(
            f"{settings.CADDY_PROXY_ADMIN_HOST}/id/{CustomProxyConfig.CADDY_ID_PREFIX}{config_id}",
            timeout=5,
        )

    def loginAsSimpleUser(self):
        User.objects.create_user(username="mohai", password="password")
        self.client.login(username="mohai", password="password")

    def create_config(self, slug: str = "custom", contents: str = VALID_CADDYFILE):
        return self.client.post(
            reverse("console:proxy.configs.list"),
            data={"slug": slug, "contents": contents},
        )

    def test_create_custom_proxy_config(self):
        self.loginUser()

        response = self.create_config()
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        config = CustomProxyConfig.objects.get(slug="custom")
        self.assertEqual(VALID_CADDYFILE, config.contents)
        self.assertTrue(config.enabled)

    def test_create_custom_proxy_config_applies_it_to_the_proxy(self):
        self.loginUser()

        response = self.create_config()
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        config_id = response.json()["id"]
        self.addCleanup(
            lambda: self.client.delete(
                reverse("console:proxy.configs.details", kwargs={"slug": "custom"})
            )
        )
        self.assertEqual(
            status.HTTP_200_OK, self.get_caddy_route(config_id).status_code
        )

    def test_create_custom_proxy_config_with_an_invalid_caddyfile(self):
        self.loginUser()

        response = self.create_config(contents=INVALID_CADDYFILE)
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIsNotNone(self.get_error_from_response(response, "contents"))
        self.assertEqual(0, CustomProxyConfig.objects.count())

    def test_create_custom_proxy_config_with_an_empty_caddyfile(self):
        self.loginUser()

        response = self.create_config(contents="   ")
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIsNotNone(self.get_error_from_response(response, "contents"))

    def test_create_custom_proxy_config_with_an_invalid_slug(self):
        self.loginUser()

        response = self.create_config(slug="not a valid slug !")
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIsNotNone(self.get_error_from_response(response, "slug"))

    def test_create_custom_proxy_config_with_a_duplicate_slug(self):
        self.loginUser()

        response = self.create_config(slug="custom")
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        response = self.create_config(slug="custom", contents=OTHER_VALID_CADDYFILE)
        self.assertEqual(status.HTTP_409_CONFLICT, response.status_code)
        self.assertEqual(1, CustomProxyConfig.objects.count())

    def test_list_custom_proxy_configs(self):
        self.loginUser()

        self.create_config(slug="custom")
        self.create_config(slug="other", contents=OTHER_VALID_CADDYFILE)

        response = self.client.get(reverse("console:proxy.configs.list"))
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(2, len(response.json()))

    def test_get_single_custom_proxy_config(self):
        self.loginUser()
        self.create_config(slug="custom")

        response = self.client.get(
            reverse("console:proxy.configs.details", kwargs={"slug": "custom"})
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(VALID_CADDYFILE, response.json()["contents"])

    def test_get_non_existing_custom_proxy_config(self):
        self.loginUser()

        response = self.client.get(
            reverse("console:proxy.configs.details", kwargs={"slug": "do-not-exist"})
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_update_custom_proxy_config(self):
        self.loginUser()
        create_response = self.create_config(slug="custom")
        config_id = create_response.json()["id"]

        response = self.client.patch(
            reverse("console:proxy.configs.details", kwargs={"slug": "custom"}),
            data={"contents": OTHER_VALID_CADDYFILE},
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        config = CustomProxyConfig.objects.get(slug="custom")
        self.assertEqual(OTHER_VALID_CADDYFILE, config.contents)
        self.addCleanup(
            lambda: self.client.delete(
                reverse("console:proxy.configs.details", kwargs={"slug": "custom"})
            )
        )
        self.assertEqual(
            status.HTTP_200_OK, self.get_caddy_route(config_id).status_code
        )

    def test_update_custom_proxy_config_with_an_invalid_caddyfile(self):
        self.loginUser()
        self.create_config(slug="custom")
        self.addCleanup(
            lambda: self.client.delete(
                reverse("console:proxy.configs.details", kwargs={"slug": "custom"})
            )
        )

        response = self.client.patch(
            reverse("console:proxy.configs.details", kwargs={"slug": "custom"}),
            data={"contents": INVALID_CADDYFILE},
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

        config = CustomProxyConfig.objects.get(slug="custom")
        self.assertEqual(VALID_CADDYFILE, config.contents)

    def test_disabling_a_custom_proxy_config_removes_it_from_the_proxy(self):
        self.loginUser()
        create_response = self.create_config(slug="custom")
        config_id = create_response.json()["id"]

        response = self.client.patch(
            reverse("console:proxy.configs.details", kwargs={"slug": "custom"}),
            data={"enabled": False},
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        config = CustomProxyConfig.objects.get(slug="custom")
        self.assertFalse(config.enabled)
        self.assertEqual(
            status.HTTP_404_NOT_FOUND, self.get_caddy_route(config_id).status_code
        )

    def test_reenabling_a_custom_proxy_config_applies_it_back_to_the_proxy(self):
        self.loginUser()
        create_response = self.create_config(slug="custom")
        config_id = create_response.json()["id"]
        self.addCleanup(
            lambda: self.client.delete(
                reverse("console:proxy.configs.details", kwargs={"slug": "custom"})
            )
        )

        self.client.patch(
            reverse("console:proxy.configs.details", kwargs={"slug": "custom"}),
            data={"enabled": False},
        )
        response = self.client.patch(
            reverse("console:proxy.configs.details", kwargs={"slug": "custom"}),
            data={"enabled": True},
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(
            status.HTTP_200_OK, self.get_caddy_route(config_id).status_code
        )

    def test_delete_custom_proxy_config(self):
        self.loginUser()
        create_response = self.create_config(slug="custom")
        config_id = create_response.json()["id"]

        response = self.client.delete(
            reverse("console:proxy.configs.details", kwargs={"slug": "custom"})
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)
        self.assertEqual(0, CustomProxyConfig.objects.count())
        self.assertEqual(
            status.HTTP_404_NOT_FOUND, self.get_caddy_route(config_id).status_code
        )

    def test_non_instance_owner_cannot_list_custom_proxy_configs(self):
        self.loginAsSimpleUser()

        response = self.client.get(reverse("console:proxy.configs.list"))
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_non_instance_owner_cannot_create_custom_proxy_configs(self):
        self.loginAsSimpleUser()

        response = self.create_config()
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)
        self.assertEqual(0, CustomProxyConfig.objects.count())

    def test_anonymous_user_cannot_create_custom_proxy_configs(self):
        response = self.create_config()
        self.assertEqual(status.HTTP_401_UNAUTHORIZED, response.status_code)
