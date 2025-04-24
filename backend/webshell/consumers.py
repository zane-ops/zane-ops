# chat/consumers.py
import json

from channels.generic.websocket import AsyncWebsocketConsumer


class WebShellConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope["url_route"]["kwargs"]["deployment_hash"]
        self.room_group_name = f"chat_{self.room_name}"

        # Join room group
        # await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        await self.accept()
        await self.send(text_data="WebShell connected.")

    async def disconnect(self, code):
        # Leave room group
        # await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        pass

    # Receive message from WebSocket
    async def receive(
        self, text_data: str | None = None, bytes_data: bytes | None = None
    ):
        # text_data_json = json.loads(text_data)
        # message = text_data_json["message"]

        # Send message to room group
        # await self.channel_layer.group_send(
        #     self.room_group_name, {"type": "chat.message", "message": message}
        # )
        await self.send(text_data=f"Echo: {text_data}")
        pass

    # # Receive message from room group
    # async def chat_message(self, event):
    #     message = event["message"]

    #     # Send message to WebSocket
    #     await self.send(text_data=json.dumps({"message": message}))
