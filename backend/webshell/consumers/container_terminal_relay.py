import asyncio
import json
import os
import shlex
import signal
import traceback
from typing import Optional, cast

from channels.generic.websocket import AsyncWebsocketConsumer
import docker
from zane_api.utils import Colors
import pty
import fcntl
import termios
import struct

from ..serializers import (
    DeploymentTerminalResizeSerializer,
)
from rest_framework.utils.serializer_helpers import ReturnDict
from zane_api.constants import WORKSPACE_SESSION_KEY
from django.contrib.auth.models import AbstractUser
from zane_api.models import WorkspaceMembership
import websockets


class GenericContainerTerminalConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def connect(self):
        await self.accept()
        # TODO
