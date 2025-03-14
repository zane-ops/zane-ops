import base64
import json
import datetime
import requests
import re
from datetime import timedelta
from typing import Sequence, Dict, Any, Union, Optional
from uuid import uuid4

from django.conf import settings
from rest_framework import status

from zane_api.utils import Colors
from .serializers import RuntimeLogsQuerySerializer, RuntimeLogsSearchSerializer
from .dtos import RuntimeLogDto


class LokiSearchClient:
    """
    A client for interacting with a Loki instance to push and search log entries.
    """

    def __init__(self, host: str):
        """
        Initializes the LokiSearchClient with the Loki host address.

        Args:
            host (str): The Loki host address including protocol and port (e.g., "http://localhost:3100").
        """
        if not isinstance(host, str):
            raise TypeError("Host must be a string.")
        self.base_url = host.rstrip("/")

    def _prepare_log_entry(self, log_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepares a single log entry for insertion into Loki.

        Args:
            log_dict (Dict[str, Any]): The dictionary representation of a log entry.

        Returns:
            Dict[str, Any]: The prepared log entry dictionary with 'id' added.
        """
        log_dict["id"] = str(uuid4())
        return log_dict

    def _create_loki_labels(self, log_dict: Dict[str, Any]) -> Dict[str, str]:
        """
        Creates a dictionary of labels for Loki from a log entry.

        Args:
            log_dict (Dict[str, Any]): The dictionary representation of a log entry.

        Returns:
            Dict[str, str]: A dictionary of labels for Loki.
        """
        return {
            "service_id": log_dict.get("service_id") or "unknown",
            "deployment_id": log_dict.get("deployment_id") or "unknown",
            "level": log_dict.get("level"),
            "source": log_dict.get("source"),
            "app": f"{settings.LOKI_APP_NAME}",
        }

    def _build_stream(self, log_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Builds a Loki stream entry from a log dictionary.

        Args:
            log_dict (Dict[str, Any]): The dictionary representation of a log entry.

        Returns:
            Dict[str, Any]: A dictionary representing a Loki stream.
        """
        labels = self._create_loki_labels(log_dict)
        ts = f"{log_dict.get('time'):.0f}"
        value = json.dumps(log_dict)
        return {"stream": labels, "values": [[ts, value]]}

    def bulk_insert(self, docs: Sequence[RuntimeLogDto]):
        """
        Push multiple log entries to Loki.
        Each document must follow the structure of RuntimeLogDto or its dict representation.
        """
        if not isinstance(docs, Sequence):
            raise TypeError("docs must be a sequence.")

        if not docs:
            return

        streams: Dict[str, Dict[str, Any]] = {}
        for doc in docs:
            if not isinstance(doc, RuntimeLogDto):
                raise TypeError("Each doc must be an instance of RuntimeLogDto")

            log_dict = doc.to_dict()
            log_dict = self._prepare_log_entry(log_dict)
            labels = self._create_loki_labels(log_dict)
            label_key = ",".join([f'{k}="{v}"' for k, v in labels.items()])
            ts = f"{log_dict.get('time'):.0f}"
            value = json.dumps(log_dict)

            if label_key not in streams:
                streams[label_key] = {"stream": labels, "values": []}
            streams[label_key]["values"].append([ts, value])

        payload = {"streams": list(streams.values())}

        try:
            response = requests.post(
                f"{self.base_url}/loki/api/v1/push", json=payload, timeout=10
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"Error sending logs to Loki: {e}")
            raise

    def insert(self, document: RuntimeLogDto):
        """
        Insert a single log entry to Loki.
        """
        if not isinstance(document, RuntimeLogDto):
            raise TypeError("document must be an instance of RuntimeLogDto")

        log_dict = document.to_dict()
        log_dict = self._prepare_log_entry(log_dict)
        stream = self._build_stream(log_dict)
        payload = {"streams": [stream]}

        try:
            response = requests.post(
                f"{self.base_url}/loki/api/v1/push", json=payload, timeout=10
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"Error sending log to Loki: {e}")
            raise

    def search(self, query: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Searches Loki for log entries based on the provided query parameters.

        Args:
            query (Optional[Dict[str, Any]]): A dictionary containing query parameters.

        Returns:
            Dict[str, Any]: A dictionary containing the search results and metadata.
        """
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
        try:
            response = requests.get(
                f"{self.base_url}/loki/api/v1/query_range",
                params=params,
                timeout=10,
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"Error querying Loki: {e}")
            raise

        data: Dict[str, Any] = response.json().get("data", {})
        stats: Dict[str, Union[int, float]] = data.get("stats", {})
        summary: Dict[str, int] = stats.get("summary", {"queueTime": 0, "execTime": 0})
        query_time_ms = (summary["queueTime"] + summary["execTime"]) / 1_000_000
        query_time_ms = float(f"{query_time_ms:.2f}")

        hits: list[dict] = []
        for stream in data.get("result", []):
            for value in stream.get("values", []):
                try:
                    log_data = json.loads(value[1])
                    hit = {
                        "id": log_data["id"],
                        "time": int(float(value[0])),
                        "level": log_data["level"],
                        "source": log_data["source"],
                        "service_id": log_data["service_id"],
                        "deployment_id": log_data["deployment_id"],
                        "content": log_data["content"],
                        "content_text": log_data["content_text"],
                        "created_at": log_data["created_at"],
                        "timestamp": int(float(value[0])),  # timestamp for pagination
                    }
                    hits.append(hit)
                except json.JSONDecodeError:
                    print(f"Failed to decode log entry: {value[1]}")
                    continue  # Skip to the next entry

        hits = sorted(
            hits, key=lambda hit: (hit["timestamp"], hit["created_at"]), reverse=True
        )

        next_cursor = None
        if len(hits) > page_size:
            extra_item = hits.pop()
            cursor_obj = {"sort": [str(extra_item["timestamp"])], "order": order}
            next_cursor = base64.b64encode(json.dumps(cursor_obj).encode()).decode()

        previous_cursor = None
        if hits:
            first_timestamp = hits[0]["timestamp"]

            prev_params = {
                "query": query_string,
                "limit": 1,
                "start": first_timestamp + 1,
                "direction": "forward",
            }
            try:
                prev_response = requests.get(
                    f"{self.base_url}/loki/api/v1/query_range",
                    params=prev_params,
                    timeout=10,
                )
                prev_response.raise_for_status()
            except requests.exceptions.RequestException as e:
                print(f"Error checking for previous logs: {e}")
                prev_exists = False
            else:
                prev_exists = False
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
                    ).isoformat(),
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

    def count(self, query: Optional[Dict[str, Any]] = None) -> int:
        """
        Counts the number of log entries in Loki matching the provided query.

        Args:
            query (Optional[Dict[str, Any]]): A dictionary containing query parameters.

        Returns:
            int: The total number of log entries matching the query.
        """
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
        try:
            response = requests.get(
                f"{self.base_url}/loki/api/v1/query_range", params=params, timeout=10
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"Error counting logs in Loki: {e}")
            raise

        result = response.json()
        total = sum(
            len(stream.get("values", []))
            for stream in result.get("data", {}).get("result", [])
        )
        print("====== END LOGS COUNT (Loki) ======")
        return total

    def delete(self, query: Optional[Dict[str, Any]] = None) -> bool:
        """
        Deletes log entries from Loki based on the provided query.

        Args:
            query (Optional[Dict[str, Any]]): A dictionary containing query parameters.

        Returns:
            bool: True if the deletion was successful.
        """
        print("====== LOGS DELETE (Loki) ======")
        filters = self._compute_filters(query)
        print(f"{filters=}")
        query_string = filters["query_string"]

        now = datetime.datetime.now()
        start = now - timedelta(days=30)
        start_timestamp_seconds = int(start.timestamp())

        params = {
            "query": query_string,
            "start": start_timestamp_seconds,
        }
        print(f"{params=}")
        try:
            response = requests.post(
                f"{self.base_url}/loki/api/v1/delete", params=params, timeout=10
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"Error deleting logs from Loki: {e}")
            raise
        print("====== END LOGS DELETE (Loki) ======")
        return True

    def _compute_filters(self, query: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Computes the filters to be used in Loki queries based on the provided query parameters.

        Args:
            query (Optional[Dict[str, Any]]): A dictionary containing query parameters.

        Returns:
            Dict[str, Any]: A dictionary containing the computed filters.
        """
        form = RuntimeLogsQuerySerializer(data=query or {})
        form.is_valid(raise_exception=True)
        search_params: dict = form.validated_data or {}  # type: ignore
        page_size = int(search_params.get("per_page", 50))

        label_selectors: list[str] = []
        if search_params.get("service_id"):
            service_id = search_params["service_id"]
            label_selectors.append(f'service_id="{service_id}"')
        if search_params.get("deployment_id"):
            deployment_id = search_params["deployment_id"]
            label_selectors.append(f'deployment_id="{deployment_id}"')
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
            time_after = search_params["time_after"]
            print(f"{time_after=}")
            dt = int(time_after.timestamp() * 1e9)
            base_selector = " ".join([base_selector, f"| time >= {dt}"])
        if search_params.get("time_before"):
            time_before = search_params["time_before"]
            print(f"{time_before=}")
            dt = int(time_before.timestamp() * 1e9)
            base_selector = " ".join([base_selector, f"| time <= {dt}"])

        now = datetime.datetime.now()
        start_ns = int((now - timedelta(days=14)).timestamp() * 10**9)
        end_ns = int(now.timestamp() * 10**9)

        order = "desc"
        cursor = search_params.get("cursor")
        cursor_data: Optional[Dict[str, Any]] = None
        if cursor:
            try:
                decoded = base64.b64decode(cursor).decode("utf-8")
                cursor_data = json.loads(decoded)
                order = cursor_data["order"]
                cursor_ts = int(cursor_data["sort"][0])

                if order == "desc":
                    end_ns = cursor_ts + 1
                else:
                    start_ns = cursor_ts
            except (
                json.JSONDecodeError,
                KeyError,
                TypeError,
                ValueError,
                base64.binascii.Error,
            ):
                print("Invalid cursor format, ignoring.")

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
