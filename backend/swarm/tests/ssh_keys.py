from django.urls import reverse
from rest_framework import status

from swarm.models import SwarmNode
from webshell.models import SSHKey
from zane_api.tests.base import AuthAPITestCase


class CreateSSHKeyForSwarmNodeViewTests(AuthAPITestCase):
    def setUp(self):
        super().setUp()
        self.node = SwarmNode.objects.create(
            hostname="zane-main",
            private_ip="10.0.0.1",
            role=SwarmNode.Role.MANAGER,
            status=SwarmNode.Status.READY,
            is_initial_install_server=True,
        )

    def test_create_ssh_key_attaches_it_to_the_node(self):
        self.loginUser()
        response = self.client.post(
            reverse("swarm:node.ssh_keys", kwargs={"id": self.node.id}),
            data={"user": "root", "slug": "my-key"},
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        key = SSHKey.objects.get(slug="my-key")
        self.assertEqual("root", key.user)
        self.assertIsNotNone(key.fingerprint)
        self.assertTrue(key.public_key.startswith("ssh-rsa "))
        self.assertIn(key, self.node.ssh_keys.all())

    def test_create_ssh_key_response_does_not_leak_private_key(self):
        self.loginUser()
        response = self.client.post(
            reverse("swarm:node.ssh_keys", kwargs={"id": self.node.id}),
            data={"user": "root", "slug": "my-key"},
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        data = response.json()
        self.assertEqual("my-key", data["slug"])
        self.assertIn("public_key", data)
        self.assertNotIn("private_key", data)

    def test_create_ssh_key_is_visible_in_node_details(self):
        self.loginUser()
        response = self.client.post(
            reverse("swarm:node.ssh_keys", kwargs={"id": self.node.id}),
            data={"user": "root", "slug": "my-key"},
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        response = self.client.get(
            reverse("swarm:node.detail", kwargs={"id": self.node.id})
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        ssh_keys = response.json()["ssh_keys"]
        self.assertEqual(1, len(ssh_keys))
        self.assertEqual("my-key", ssh_keys[0]["slug"])

    def test_create_ssh_key_with_existing_slug_conflicts(self):
        self.loginUser()
        public_key, private_key = SSHKey.create_key_pair()
        SSHKey.objects.create(
            user="root",
            slug="my-key",
            public_key=public_key,
            private_key=private_key,
        )
        response = self.client.post(
            reverse("swarm:node.ssh_keys", kwargs={"id": self.node.id}),
            data={"user": "root", "slug": "my-key"},
        )
        self.assertEqual(status.HTTP_409_CONFLICT, response.status_code)
        self.assertEqual(1, SSHKey.objects.count())

    def test_create_ssh_key_validates_unix_username(self):
        self.loginUser()
        response = self.client.post(
            reverse("swarm:node.ssh_keys", kwargs={"id": self.node.id}),
            data={"user": "not a valid user!", "slug": "my-key"},
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIsNotNone(self.get_error_from_response(response, "user"))
        self.assertEqual(0, SSHKey.objects.count())

    def test_create_ssh_key_for_non_existent_node(self):
        self.loginUser()
        response = self.client.post(
            reverse("swarm:node.ssh_keys", kwargs={"id": "node_doesnotexist"}),
            data={"user": "root", "slug": "my-key"},
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)
        self.assertEqual(0, SSHKey.objects.count())

    def test_create_ssh_key_requires_instance_owner(self):
        response = self.client.post(
            reverse("swarm:node.ssh_keys", kwargs={"id": self.node.id}),
            data={"user": "root", "slug": "my-key"},
        )
        self.assertEqual(status.HTTP_401_UNAUTHORIZED, response.status_code)
        self.assertEqual(0, SSHKey.objects.count())
