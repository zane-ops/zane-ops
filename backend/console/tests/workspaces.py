from datetime import timedelta
from typing import cast

from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from zane_api.tests.base import AuthAPITestCase
from zane_api.utils import jprint
from console.models import PasswordResetToken


class DeleteWorkspaceViewTests(AuthAPITestCase):
    pass
