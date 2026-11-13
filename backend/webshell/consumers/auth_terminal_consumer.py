from channels.generic.websocket import AsyncWebsocketConsumer
from zane_api.utils import Colors

from zane_api.constants import WORKSPACE_SESSION_KEY
from django.contrib.auth.models import AbstractUser
from zane_api.models import WorkspaceMembership
from django.conf import settings


class AuthenticatedTerminalConsumer(AsyncWebsocketConsumer):
    async def check_for_internal_app(self):
        headers = dict(self.scope["headers"])
        if b"authorization" in headers:
            auth: list[str] = headers.get(b"authorization", b" ").decode().split(" ")
            if len(auth) == 2:
                auth_type, key = auth
                if auth_type == "Internal" and key == settings.SECRET_KEY:
                    return True

        await self.send(
            f"{Colors.RED}You do not have permission to access this resource{Colors.ENDC}\n\r",
            close=True,
        )
        return False

    async def check_for_workspace_roles(self, role: int):
        self.user: AbstractUser = self.scope["user"]  # type: ignore
        self.session = self.scope["session"]  # type: ignore
        workspace_id = self.session.get(WORKSPACE_SESSION_KEY)

        qs = WorkspaceMembership.objects.filter(
            user=self.user,
            role__gte=role,
        ).select_related("workspace")

        if workspace_id:
            qs = qs.filter(workspace_id=workspace_id)

        membership = await qs.afirst()

        if not membership:
            await self.send(
                f"{Colors.RED}You do not have permission to access this resource{Colors.ENDC}\n\r",
                close=True,
            )

        # return membership is not None and membership.role >= WorkspaceRole.MEMBER
        return membership
