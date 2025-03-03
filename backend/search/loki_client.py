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
        """
        Search logs in Loki using parameters similar to the Elasticsearch client.
        The query dict is processed via RuntimeLogsQuerySerializer to extract filters,
        which are then converted into a LogQL query.
        Pagination (cursor) is not supported by Loki, so results are returned as-is.
        """
        print("====== LOGS SEARCH (Loki) ======")
        data = self._compute_filters(query)
        query_string = data["query_string"]
        limit = data["page_size"]
        start_ns = data["start"]
        end_ns = data["end"]

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
        total = 0
        # Loki returns data as streams; each stream contains a list of log entries.
        for stream in result.get("data", {}).get("result", []):
            for ts, log_line in stream.get("values", []):
                total += 1
                try:
                    log_data = json.loads(log_line)
                except Exception:
                    log_data = {"raw": log_line}
                # Reformat the log entry to mimic the expected output
                hit = {
                    "id": log_data.get("id", ""),
                    "time": log_data.get("time", ""),
                    "level": log_data.get("level", ""),
                    "source": log_data.get("source", ""),
                    "service_id": log_data.get("service_id", ""),
                    "deployment_id": log_data.get("deployment_id", ""),
                    "content": log_data.get("content", ""),
                    "content_text": log_data.get("content_text", ""),
                }
                hits.append(hit)

        serializer = RuntimeLogsSearchSerializer(
            {
                "query_time_ms": query_time_ms,
                "total": total,
                "results": hits,
                "next": None,
                "previous": None,
            }
        )

        print(
            f"Found {Colors.BLUE}{total}{Colors.ENDC} logs in Loki in {Colors.GREEN}{query_time_ms}ms{Colors.ENDC}"
        )
        print("====== END LOGS SEARCH (Loki) ======")
        return serializer.data

    def count(self, query: dict | None = None) -> int:
        """
        Count logs matching the query.
        Since Loki does not provide a direct count endpoint, we perform a search
        with a high limit and count the returned log entries.
        """
        data = self._compute_filters(query)
        query_string = data["query_string"]
        params = {
            "query": query_string,
            "limit": 10000,  # adjust limit if needed
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
        """
        Compute a LogQL query from the input query parameters.
        Uses RuntimeLogsQuerySerializer to validate and extract filters.
        Converts filters into a label selector and optional pipeline stages.
        """
        form = RuntimeLogsQuerySerializer(data=query or {})
        form.is_valid(raise_exception=True)
        search_params: dict = form.validated_data or {}  # type: ignore
        page_size = int(search_params.get("per_page", 50))

        # Build label selectors from provided filters.
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

        # Convert time range filters to Unix epoch in nanoseconds.
        start_ns = 0
        end_ns = int(time.time() * 1e9)
        if search_params.get("time_after"):
            dt = datetime.datetime.fromisoformat(search_params["time_after"])
            start_ns = int(dt.timestamp() * 1e9)
        if search_params.get("time_before"):
            dt = datetime.datetime.fromisoformat(search_params["time_before"])
            end_ns = int(dt.timestamp() * 1e9)

        # Append a pipeline stage to search within the log's content_text if a query is provided.
        text_query = ""
        if search_params.get("query"):
            term = search_params["query"]
            # This regex matches any log whose content_text contains the search term.
            text_query = f' | json | content_text =~ ".*{term}.*"'

        query_string = base_selector + text_query
        return {
            "query_string": query_string,
            "page_size": page_size,
            "start": start_ns,
            "end": end_ns,
        }
