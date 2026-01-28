from django.urls import reverse
from rest_framework import status
import responses
import requests
from django.conf import settings

from zane_api.models import Environment, SharedEnvVariable
from ..models import ComposeStack, ComposeStackChange, ComposeStackEnvOverride
from .fixtures import (
    DOCKER_COMPOSE_MINIMAL,
    DOCKER_COMPOSE_SIMPLE_DB,
    DOCKER_COMPOSE_WITH_X_ENV_IN_URLS,
    DOCKER_COMPOSE_WITH_PLACEHOLDERS,
    DOCKER_COMPOSE_WEB_SERVICE,
    DOCKER_COMPOSE_WITH_SHARED_ENV_REFERENCES,
    DOCKER_COMPOSE_WITHOUT_SHARED_ENV_REFERENCES,
    DOCKER_COMPOSE_WITH_SHARED_ENV_OUTSIDE_X_ZANE_ENV,
)
from typing import cast
from zane_api.utils import jprint
from temporal.helpers import ZaneProxyClient

from .stacks import ComposeStackAPITestBase
from ..dtos import ComposeStackUrlRouteDto


class CloneEnvironmentWithStackViewTests(ComposeStackAPITestBase):
    def test_clone_environment_should_clone_included_stacks(self):
        pass

    async def test_clone_environment_with_deploy_true_should_deploy_included_stacks(
        self,
    ):
        pass

    async def test_clone_environment_without_deploy_true_should_not_deploy_included_stacks(
        self,
    ):
        pass
