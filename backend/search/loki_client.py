import base64
import json
import time
import datetime
import requests
from typing import Iterator
from zane_api.utils import Colors
from .serializers import RuntimeLogsQuerySerializer, RuntimeLogsSearchSerializer
from .dtos import RuntimeLogDto


class LokiSearchClient:
    def __init__(self, host: str):
        # host should include the protocol and port, e.g., "http://localhost:3100"
        self.base_url = host.rstrip("/")

    def bulk_insert(self, docs: Iterator[RuntimeLogDto | dict]):
        """
        Push multiple log entries to Loki.
        Each document must follow the structure of RuntimeLogDto or its dict representation.
        """
        streams = {}
        for doc in docs:
            # Convert RuntimeLogDto to dict if needed
            log_dict = doc.to_dict() if isinstance(doc, RuntimeLogDto) else doc

            # Define labels for Loki from key fields.
            labels = {
                "service_id": log_dict.get("service_id") or "unknown",
                "deployment_id": log_dict.get("deployment_id") or "unknown",
                "level": log_dict.get("level"),
                "source": log_dict.get("source"),
            }
            # Construct a label selector string
            label_key = ",".join([f'{k}="{v}"' for k, v in labels.items()])
            ts = str(log_dict.get("time"))
            value = json.dumps(log_dict)
            if label_key not in streams:
                streams[label_key] = {"stream": labels, "values": []}
            streams[label_key]["values"].append([ts, value])

        payload = {"streams": list(streams.values())}
        response = requests.post(f"{self.base_url}/loki/api/v1/push", json=payload)
        if response.status_code not in (200, 204):
            raise Exception(f"Bulk insert failed: {response.text}")

    def insert(self, document: dict | RuntimeLogDto):
        """
        Insert a single log entry to Loki.
        """
        log_dict = (
            document.to_dict() if isinstance(document, RuntimeLogDto) else document
        )

        labels = {
            "service_id": log_dict.get("service_id") or "unknown",
            "deployment_id": log_dict.get("deployment_id") or "unknown",
            "level": log_dict.get("level"),
            "source": log_dict.get("source"),
        }
        ts = str(log_dict.get("time"))
        payload = {
            "streams": [{"stream": labels, "values": [[ts, json.dumps(log_dict)]]}]
        }
        response = requests.post(f"{self.base_url}/loki/api/v1/push", json=payload)
        if response.status_code not in (200, 204):
            raise Exception(f"Insert failed: {response.text}")

    def search(self, query: dict | None = None):
        print("====== LOGS SEARCH (Loki) ======")
        data = self._compute_filters(query)
        query_string = data["query_string"]
        limit = data["page_size"]
        start_ns = data["start"]
        end_ns = data["end"]
        prev_cursor = data.get("prev_cursor")

        params = {
            "query": query_string,
            "limit": limit,
            "start": start_ns,
            "end": end_ns,
        }

        start_req = time.time()
        response = requests.get(
            f"{self.base_url}/loki/api/v1/query_range", params=params
        )
        query_time_ms = int((time.time() - start_req) * 1000)
        if response.status_code != 200:
            raise Exception(f"Search failed: {response.text}")

        result = response.json()
        hits = []
        # Loki returns streams; each stream contains a list of log entries.
        for stream in result.get("data", {}).get("result", []):
            for ts, log_line in stream.get("values", []):
                try:
                    log_data = json.loads(log_line)
                except Exception:
                    log_data = {"raw": log_line}
                hit = {
                    "id": log_data.get("id", ""),
                    "time": log_data.get("time", ""),
                    "level": log_data.get("level", ""),
                    "source": log_data.get("source", ""),
                    "service_id": log_data.get("service_id", ""),
                    "deployment_id": log_data.get("deployment_id", ""),
                    "content": log_data.get("content", ""),
                    "content_text": log_data.get("content_text", ""),
                    "timestamp": int(ts),  # timestamp for pagination
                }
                hits.append(hit)

        # Ensure ascending order by timestamp
        hits = sorted(hits, key=lambda x: x["timestamp"])
        total = len(hits)

        # Implement custom cursor pagination:
        next_cursor = None
        if total == limit and total > 0:
            last_timestamp = hits[-1]["timestamp"]
            cursor_obj = {"last": last_timestamp}
            next_cursor = base64.b64encode(json.dumps(cursor_obj).encode()).decode()

        # For simplicity, previous cursor is returned if provided in the query.
        previous_cursor = prev_cursor

        serializer = RuntimeLogsSearchSerializer(
            {
                "query_time_ms": query_time_ms,
                "total": total,
                "results": [
                    {
                        "id": hit["id"],
                        "time": hit["time"],
                        "level": hit["level"],
                        "source": hit["source"],
                        "service_id": hit["service_id"],
                        "deployment_id": hit["deployment_id"],
                        "content": {"raw": hit["content"]},
                        "content_text": hit["content_text"],
                    }
                    for hit in hits
                ],
                "next": next_cursor,
                "previous": previous_cursor,
            }
        )

        print(
            f"Found {Colors.BLUE}{total}{Colors.ENDC} logs in Loki in {Colors.GREEN}{query_time_ms}ms{Colors.ENDC}"
        )
        print("====== END LOGS SEARCH (Loki) ======")
        return serializer.data

    def count(self, query: dict | None = None) -> int:
        data = self._compute_filters(query)
        query_string = data["query_string"]
        params = {
            "query": query_string,
            "limit": 10000,
            "start": data["start"],
            "end": data["end"],
        }
        response = requests.get(
            f"{self.base_url}/loki/api/v1/query_range", params=params
        )
        if response.status_code != 200:
            raise Exception(f"Count failed: {response.text}")
        result = response.json()
        total = sum(
            len(stream.get("values", []))
            for stream in result.get("data", {}).get("result", [])
        )
        return total

    def _compute_filters(self, query: dict | None = None):
        form = RuntimeLogsQuerySerializer(data=query or {})
        form.is_valid(raise_exception=True)
        search_params: dict = form.validated_data or {}  # type: ignore
        page_size = int(search_params.get("per_page", 50))

        label_selectors = []
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
        base_selector = (
            "{" + ",".join(label_selectors) + "}"
            if label_selectors
            else '{level=~".*"}'
        )

        # Default time range: start=0, end=now.
        start_ns = 0
        end_ns = int(time.time() * 1e9)
        if search_params.get("time_after"):
            dt = datetime.datetime.fromisoformat(search_params["time_after"])
            start_ns = int(dt.timestamp() * 1e9)
        if search_params.get("time_before"):
            dt = datetime.datetime.fromisoformat(search_params["time_before"])
            end_ns = int(dt.timestamp() * 1e9)

        # Default order.
        order = "desc"
        cursor = search_params.get("cursor")
        if cursor:
            try:
                decoded = base64.b64decode(cursor).decode("utf-8")
                cursor_data = json.loads(decoded)
                # Expecting sort to be a list with one timestamp value.
                last_timestamp = int(cursor_data["sort"][0])
                order = cursor_data["order"]
                if order == "asc":
                    start_ns = last_timestamp + 1
                else:
                    end_ns = last_timestamp - 1
            except Exception:
                pass

        text_query = ""
        if search_params.get("query"):
            term = search_params["query"]
            text_query = f' | json | content_text =~ ".*{term}.*"'

        query_string = base_selector + text_query

        return {
            "query_string": query_string,
            "page_size": page_size,
            "start": start_ns,
            "end": end_ns,
            "order": order,
            "cursor": cursor,
        }
