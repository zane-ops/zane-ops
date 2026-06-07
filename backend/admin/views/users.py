from typing import cast

from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status

from zane_api.models import Workspace, WorkspaceMembership, WorkspaceRole, Project
from zane_api.constants import WORKSPACE_SESSION_KEY
from zane_api.tests.base import AuthAPITestCase
from zane_api.utils import jprint


class ResetUserPasswordViewTests(AuthAPITestCase):
    pass
