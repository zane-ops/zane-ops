import base64
import json
import datetime
import requests
from datetime import timedelta
from typing import Sequence
from zane_api.utils import Colors
from .serializers import RuntimeLogsQuerySerializer, RuntimeLogsSearchSerializer
from .dtos import RuntimeLogDto
from django.conf import settings
from uuid import uuid4
import re
from rest_framework import status


class LokiSearchClient:
    def __init__(self, host: str):
        # host should include the protocol and port, e.g., "http://localhost:3100"
        self.base_url = host.rstrip("/")

    def bulk_insert(self, docs: Sequence[RuntimeLogDto]):
        """
        Push multiple log entries to Loki.
        Each document must follow the structure of RuntimeLogDto or its dict representation.
        """
        if len(docs) == 0:
            return
        streams = {}
        for doc in docs:
            # Convert RuntimeLogDto to dict if needed
            log_dict = doc.to_dict()
            log_dict["id"] = str(uuid4())

            # Define labels for Loki from key fields.
            labels = {
                "service_id": log_dict.get("service_id") or "unknown",
                "deployment_id": log_dict.get("deployment_id") or "unknown",
                "level": log_dict.get("level"),
                "source": log_dict.get("source"),
                "app": f"{settings.LOKI_APP_NAME}",
            }
            # Construct a label selector string
            label_key = ",".join([f'{k}="{v}"' for k, v in labels.items()])
            ts = f"{log_dict.get('time'):.0f}"
            value = json.dumps(log_dict)
            if label_key not in streams:
                streams[label_key] = {"stream": labels, "values": []}
            streams[label_key]["values"].append([ts, value])

        payload = {"streams": list(streams.values())}
        response = requests.post(
            f"{self.base_url}/loki/api/v1/push",
            json=payload,
            stream=False,
        )
        response.raise_for_status()

    def insert(self, document: RuntimeLogDto):
        """
        Insert a single log entry to Loki.
        """
        log_dict = document.to_dict()
        log_dict["id"] = str(uuid4())

        labels = {
            "service_id": log_dict.get("service_id") or "unknown",
            "deployment_id": log_dict.get("deployment_id") or "unknown",
            "level": log_dict.get("level"),
            "source": log_dict.get("source"),
            "app": f"{settings.LOKI_APP_NAME}",
        }
        ts = f"{log_dict.get('time'):.0f}"
        payload = {
            "streams": [{"stream": labels, "values": [[ts, json.dumps(log_dict)]]}]
        }
        response = requests.post(
            f"{self.base_url}/loki/api/v1/push",
            json=payload,
            stream=False,
        )
        response.raise_for_status()

    def search(self, query: dict | None = None):
        print("\n====== LOGS SEARCH (Loki) ======")
        filters = self._compute_filters(query)
        print(f"filters={Colors.GREY}{filters}{Colors.ENDC}")
        query_string = filters["query_string"]
        page_size = filters["page_size"]
        start_ns = filters["start"]
        end_ns = filters["end"]
        order = filters["order"]

        params = {
            "query": query_string,
            "limit": page_size + 1,
            "start": start_ns,
            "end": end_ns,
            "direction": "backward",
        }

        print(f"params={Colors.GREY}{params}{Colors.ENDC}")
        response = requests.get(
            f"{self.base_url}/loki/api/v1/query_range",
            params=params,
            stream=False,
        )
        response.raise_for_status()

        summary = (
            response.json()
            .get("data", {})
            .get("stats", {})
            .get("summary", {"queueTime": 0, "execTime": 0})
        )
        query_time_ms = (summary["queueTime"] + summary["execTime"]) * 1000
        query_time_ms = float(f"{query_time_ms:.2f}")
        result = response.json()
        hits: list[dict] = []
        # Loki returns streams; each stream contains a list of log entries.
        for stream in result.get("data", {}).get("result", []):
            log_data = stream["stream"]
            hit = {
                "id": log_data["id"],
                "time": int(float(log_data["time"])),
                "level": log_data["level"],
                "source": log_data["source"],
                "service_id": log_data["service_id"],
                "deployment_id": log_data["deployment_id"],
                "content": log_data["content"],
                "content_text": log_data["content_text"],
                "created_at": log_data["created_at"],
                "timestamp": int(float(log_data["time"])),  # timestamp for pagination
            }
            hits.append(hit)

        hits = sorted(
            hits, key=lambda hit: (hit["timestamp"], hit["created_at"]), reverse=True
        )

        # Generate next cursor if total equals page size.
        next_cursor = None
        if len(hits) > page_size:
            # Pop the extra item to avoid overlap.
            extra_item = hits.pop()
            cursor_obj = {"sort": [str(extra_item["timestamp"])], "order": order}
            next_cursor = base64.b64encode(json.dumps(cursor_obj).encode()).decode()

        # Generate previous cursor only if there is at least one log in the inverse order.
        previous_cursor = None
        if hits:
            first_timestamp = hits[0]["timestamp"]
            # Prepare parameters to check existence of a previous log.
            prev_params = {
                "query": query_string,
                "limit": 1,
                "start": first_timestamp + 1,
                "direction": "forward",
            }

            prev_response = requests.get(
                f"{self.base_url}/loki/api/v1/query_range", params=prev_params
            )
            prev_exists = False
            if prev_response.status_code == status.HTTP_200_OK:
                prev_result = prev_response.json()
                for stream in prev_result.get("data", {}).get("result", []):
                    if stream.get("values") and len(stream["values"]) > 0:
                        prev_exists = True
                        break
            if prev_exists:
                previous_cursor_obj = {
                    "sort": [str(first_timestamp)],
                    "order": "asc",
                }
                previous_cursor = base64.b64encode(
                    json.dumps(previous_cursor_obj).encode()
                ).decode()

        data = {
            "query_time_ms": query_time_ms,
            "results": [
                {
                    "id": hit["id"],
                    "time": datetime.datetime.fromtimestamp(
                        (hit["time"] // 1_000) / 1e6
                    ).isoformat(),  # remove nanoseconds, then divide by 1 million to get microseconds
                    "level": hit["level"],
                    "source": hit["source"],
                    "service_id": hit["service_id"],
                    "deployment_id": hit["deployment_id"],
                    "content": hit["content"],
                    "content_text": hit["content_text"],
                    "timestamp": hit["timestamp"],
                }
                for hit in hits
            ],
            "next": next_cursor,
            "previous": previous_cursor,
        }

        serializer = RuntimeLogsSearchSerializer(data)

        print(
            f"Found {Colors.BLUE}{len(hits)}{Colors.ENDC} logs in Loki in {Colors.GREEN}{query_time_ms}ms{Colors.ENDC}"
        )
        print("====== END LOGS SEARCH (Loki) ======\n")
        return serializer.data

    def count(self, query: dict | None = None) -> int:
        filters = self._compute_filters(query)
        print("====== LOGS COUNT (Loki) ======")
        print(f"{filters=}")
        query_string = filters["query_string"]
        params = {
            "query": query_string,
            "limit": 5000,
            "start": filters["start"],
            "end": filters["end"],
        }
        response = requests.get(
            f"{self.base_url}/loki/api/v1/query_range", params=params
        )
        if response.status_code != status.HTTP_200_OK:
            raise Exception(f"Count failed: {response.text}")
        result = response.json()
        total = sum(
            len(stream.get("values", []))
            for stream in result.get("data", {}).get("result", [])
        )
        print("====== END LOGS COUNT (Loki) ======")
        return total

    def delete(self, query: dict | None = None):
        print("====== LOGS DELETE (Loki) ======")
        filters = self._compute_filters(query)
        print(f"{filters=}")
        query_string = filters["query_string"]

        now = datetime.datetime.now()
        start = now - timedelta(days=30)
        params = {
            "query": query_string,
            "start": int(start.timestamp()),
        }
        print(f"{params=}")

        response = requests.post(f"{self.base_url}/loki/api/v1/delete", params=params)
        response.raise_for_status()
        print("====== END LOGS DELETE (Loki) ======")
        return True

    def _compute_filters(self, query: dict | None = None):
        form = RuntimeLogsQuerySerializer(data=query or {})
        form.is_valid(raise_exception=True)
        search_params: dict = form.validated_data or {}  # type: ignore
        page_size = int(search_params.get("per_page", 50))

        label_selectors: list[str] = []
        if search_params.get("service_id"):
            label_selectors.append(f'service_id="{search_params["service_id"]}"')
        if search_params.get("deployment_id"):
            label_selectors.append(f'deployment_id="{search_params["deployment_id"]}"')
        if search_params.get("level"):
            levels = search_params["level"]
            if isinstance(levels, list):
                label_selectors.append('level=~"(' + "|".join(levels) + ')"')
            else:
                label_selectors.append(f'level="{levels}"')
        if search_params.get("source"):
            sources = search_params["source"]
            if isinstance(sources, list):
                label_selectors.append('source=~"(' + "|".join(sources) + ')"')
            else:
                label_selectors.append(f'source="{sources}"')

        label_selectors.append(f'app="{settings.LOKI_APP_NAME}"')
        base_selector = "{" + ",".join(label_selectors) + "} | json"

        if search_params.get("time_after"):
            print(f"{search_params['time_after']=}")
            dt = search_params["time_after"]
            dt = int(dt.timestamp() * 1e9)
            base_selector = " ".join([base_selector, f"| time >= {dt}"])
        if search_params.get("time_before"):
            print(f"{search_params['time_before']=}")
            dt = search_params["time_before"]
            dt = int(dt.timestamp() * 1e9)
            base_selector = " ".join([base_selector, f"| time <= {dt}"])

        # Default time range: start=14 days ago, end=now.
        now = datetime.datetime.now()
        start_ns = int((now - timedelta(days=14)).timestamp() * 10**9)
        end_ns = int(now.timestamp() * 10**9)

        # Default order.
        order = "desc"
        cursor = search_params.get("cursor")
        cursor_data = None
        if cursor:
            try:
                decoded = base64.b64decode(cursor).decode("utf-8")
                cursor_data = json.loads(decoded)
                # Expecting sort to be a list with one timestamp value.
                order = cursor_data["order"]
                cursor_ts = int(cursor_data["sort"][0])

                if order == "desc":
                    # start : 0
                    end_ns = (
                        cursor_ts + 1
                    )  # we set `+1` here because loki does not include logs containing the end timestamp
                else:
                    start_ns = cursor_ts
                    # end : now
            except Exception:
                pass

        text_query = ""
        if search_params.get("query"):
            term: str = search_params["query"]
            term = re.escape(term).replace("\\", "\\\\").replace('"', '\\"')
            text_query = '| line_format "{{.content_text}}" |~ "(?i)' + f"{term}" + '"'

        query_string = " ".join([base_selector, text_query])
        print(f"query_string={Colors.GREY}{query_string}{Colors.ENDC}")
        return {
            "query_string": query_string,
            "page_size": page_size,
            "start": start_ns,
            "end": end_ns,
            "order": order,
            "cursor": cursor,
            "cursor_data": cursor_data,
        }
