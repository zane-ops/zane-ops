import json
from django.conf import settings
import requests

from .utils import jprint

from .views.serializers import (
    DeploymentLogsQuerySerializer,
    DeploymentLogsResponseSerializer,
)
from rest_framework.request import Request
import base64


class QuickwitClient:
    @classmethod
    def search(cls, request: Request, deployment_hash: str) -> dict:
        form = DeploymentLogsQuerySerializer(data=request.query_params)
        if form.is_valid(raise_exception=True):
            per_page = form.data["per_page"]
            cursor = form.data.get("cursor")

            quickwit_api_search_query = f"deployment_id:{deployment_hash}"

            if cursor:
                cursor = base64.b64decode(cursor).decode()
                cursor = json.loads(cursor)
                # Cursor based pagination is basically ✨magic✨, this algorithm is based on this video : https://youtu.be/zwDIN04lIpc?si=lpb4UQdfTAv-w1NT&t=560
                if cursor["direction"] == "forward":
                    quickwit_api_search_query = (
                        f'{quickwit_api_search_query} AND time:<={cursor["time"]}'
                    )

            print(f"{quickwit_api_search_query=}")
            response = requests.post(
                f"{settings.QUICKWIT_API_URL}/api/v1/{settings.LOGS_INDEX_NAME}/search",
                json={
                    "query": quickwit_api_search_query,
                    "max_hits": per_page + 1,
                    # we can pass -time,-created_at to quickwit but quickwit works inversely
                    # so the default sorting direction is descending
                    "sort_by": "time",
                },
            )

            jprint(response.json())
            response.raise_for_status()

            logs_response = response.json()

            next_cursor = None
            results: list[dict] = logs_response["hits"]
            if len(results) > per_page:
                next_item = results.pop()
                next_cursor = json.dumps(
                    {
                        "time": next_item["time"],
                        "created_at": next_item["created_at"],
                        "direction": "forward",
                    }
                )
                next_cursor = base64.b64encode(next_cursor.encode()).decode()

            serializer = DeploymentLogsResponseSerializer(
                dict(
                    results=logs_response["hits"],
                    next=next_cursor,
                    query_time_ms=logs_response["elapsed_time_micros"] / 1000,
                )
            )
            return serializer.data
