from .base import AuthAPITestCase
from django.urls import reverse
from ..models import (
    Project,
    DockerDeployment,
    DockerRegistryService,
    DockerDeploymentChange,
    Volume,
    PortConfiguration,
    URL,
    HealthCheck,
    DockerEnvVariable,
)
from rest_framework import status


class DockerServiceNetworksTests(AuthAPITestCase):
    def test_apply_simple_changes(self):
        self.assertTrue(False)
