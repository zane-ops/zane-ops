from datetime import datetime, timezone
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

            base_search_query = f"deployment_id:{deployment_hash}"
            search_query_with_cursor = base_search_query

            if cursor:
                cursor = base64.b64decode(cursor).decode()
                cursor = json.loads(cursor)
                # Cursor based pagination is basically ✨magic✨, this algorithm is based on this video : https://youtu.be/zwDIN04lIpc?si=lpb4UQdfTAv-w1NT&t=560
                if cursor["direction"] == "forward":
                    search_query_with_cursor = (
                        f'{search_query_with_cursor} AND time:<={cursor["time"]}'
                    )
                else:
                    search_query_with_cursor = (
                        f'{search_query_with_cursor} AND time:>={cursor["time"]}'
                    )

            print(f"{base_search_query=}")
            print(f"{search_query_with_cursor=}")
            response = requests.post(
                f"{settings.QUICKWIT_API_URL}/api/v1/{settings.LOGS_INDEX_NAME}/search",
                json={
                    "query": search_query_with_cursor,
                    "max_hits": per_page + 1,
                    # we can pass -time to quickwit but quickwit works inversely
                    # so the default sorting direction is descending, and passing -time will make it ascending
                    "sort_by": "time",
                },
            )

            response.raise_for_status()

            next_cursor = None
            results: list[dict] = response.json()["hits"]
            if len(results) > per_page:
                next_item = results.pop()
                next_cursor = json.dumps(
                    {
                        "time": next_item["time"],
                        "direction": "forward",
                    }
                )
                next_cursor = base64.b64encode(next_cursor.encode()).decode()

            previous_cursor = None

            if len(results) > 0:
                # the most recent item is the first, we try to see if there are more logs after this
                # so we can generate a previous cursor if needed
                first_item = results[0]

                # it seems like if we use the quickwit `time:>` operator, it might return an empty list because the sorting
                # precision is in seconds, but with the `time:>=` operator, the sorting is in microseconds
                previous_query = f"{base_search_query} AND time:>={first_item['time']}"
                backward_response = requests.post(
                    f"{settings.QUICKWIT_API_URL}/api/v1/{settings.LOGS_INDEX_NAME}/search",
                    json={
                        "query": previous_query,
                        "max_hits": 2,
                        "sort_by": "time",
                    },
                )

                backward_response.raise_for_status()

                print(f"{previous_query=}")
                jprint(backward_response.json())

                backward_results: list[dict] = backward_response.json()["hits"]
                if len(backward_results) > 1:
                    previous_cursor = json.dumps(
                        {
                            "time": first_item["time"],
                            "direction": "backward",
                        }
                    )
                    previous_cursor = base64.b64encode(
                        previous_cursor.encode()
                    ).decode()

            results = results
            query_time_ms = response.json()["elapsed_time_micros"] / 1000

            serializer = DeploymentLogsResponseSerializer(
                dict(
                    next=next_cursor,
                    previous=previous_cursor,
                    results=[
                        dict(
                            id=result["id"],
                            service_id=result["service_id"],
                            deployment_id=result["deployment_id"],
                            content=result["content"],
                            content_text=result["content_text"],
                            level=result["level"],
                            source=result["source"],
                            time=datetime.fromtimestamp(
                                # we divide by 1e6 because the time is returned in microseconds
                                result["time"] / 1e6,
                                timezone.utc,
                            ).isoformat(),
                            created_at=datetime.fromtimestamp(
                                result["created_at"] / 1e6, timezone.utc
                            ).isoformat(),
                        )
                        for result in results
                    ],
                    query_time_ms=query_time_ms,
                )
            )
            return serializer.data
