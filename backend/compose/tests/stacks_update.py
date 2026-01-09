from django.urls import reverse
import os
import responses
from rest_framework import status
from unittest.mock import patch

from zane_api.models import Environment
from zane_api.tests.base import FakeDockerClient
from ..models import (
    ComposeStack,
    ComposeStackChange,
    ComposeStackDeployment,
    ComposeStackEnvOverride,
)
from .fixtures import (
    DOCKER_COMPOSE_MINIMAL,
    DOCKER_COMPOSE_SIMPLE_DB,
    DOCKER_COMPOSE_WEB_SERVICE,
    DOCKER_COMPOSE_MULTIPLE_ROUTES,
    DOCKER_COMPOSE_WITH_PLACEHOLDERS,
    DOCKER_COMPOSE_WITH_INLINE_CONFIGS,
)
from typing import cast
from zane_api.utils import jprint
from ..dtos import ComposeStackServiceStatus
import requests
from temporal.helpers import ZaneProxyClient
from django.conf import settings
from temporal.schedules import MonitorComposeStackWorkflow
from temporal.activities import ComposeStackActivities
from compose.dtos import ComposeStackSnapshot
from temporalio import activity
from temporal.shared import ComposeStackBuildDetails
from compose.dtos import ComposeStackUrlRouteDto


from .stacks import ComposeStackAPITestBase


class ComposeStackRequestUpdateViewTests(ComposeStackAPITestBase):
    def test_update_content_request_(self):
        pass
