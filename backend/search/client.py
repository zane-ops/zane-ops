import base64
import json
from typing import Generator
from elasticsearch import Elasticsearch, helpers
from zane_api.utils import Colors
from .serializers import RuntimeLogsQuerySerializer, RuntimeLogsSearchSerializer
from .dtos import RuntimeLogDto


class SearchClient:
    """
    TODO :
    - limit the system logs to less than 30k characters
    - we might need to explore breaking service logs into pieces if they exceed the limit when indexing
    """

    def __init__(self, host: str):
        self.es = Elasticsearch(host, api_key="")

    def bulk_insert(self, docs: list | Generator):
        from django.conf import settings

        helpers.bulk(self.es, docs, refresh=settings.TESTING)

    def insert(self, index_name: str, document: dict | RuntimeLogDto):
        from django.conf import settings

        document = (
            document.to_es_dict() if isinstance(document, RuntimeLogDto) else document
        )
        self.es.index(index=index_name, document=document, refresh=settings.TESTING)

    def search(self, index_name: str, query: dict = None):
        print(f"====== LOGS SEARCH ======")
        print(f"Index: {Colors.BLUE}{index_name}{Colors.ENDC}")
        data = self._compute_filters(query)

        filters = data["filters"]
        search_after = data["search_after"]
        order = data["order"]
        page_size = data["page_size"]

        result = self.es.search(
            index=index_name,
            size=page_size + 1,
            search_after=search_after,
            sort=[
                {
                    "time": {
                        "order": order,
                        "format": "strict_date_optional_time_nanos",
                        "numeric_type": "date_nanos",
                    }
                }
            ],
            query=(
                {"bool": {"filter": filters}} if len(filters) > 0 else {"match_all": {}}
            ),
        )

        hits = (
            result["hits"]["hits"]
            if order == "desc"
            else list(
                reversed(result["hits"]["hits"])
            )  # we reverse the list because we always want the oldest logs first
        )
        total = result["hits"]["total"]["value"]
        query_time_ms = result["took"]
        next_cursor = None
        prev_cursor = None

        if len(hits) > page_size:
            # the last hit is used for pagination,
            # to check if there are more results,
            # so we remove it from the results
            hits.pop()

            next_cursor = json.dumps(
                {
                    "sort": hits[-1]["sort"],
                    "order": "desc",
                }
            )
            next_cursor = base64.b64encode(next_cursor.encode()).decode()

        if len(hits) > 0:
            # the most recent item is the first, we try to see if there are more logs after this
            # so we can generate a previous cursor if needed
            first_item = hits[0]

            result = self.es.search(
                index=index_name,
                size=1,
                search_after=first_item["sort"],
                sort=[
                    {
                        "time": {
                            "order": "asc",
                            "format": "strict_date_optional_time_nanos",
                            "numeric_type": "date_nanos",
                        }
                    }
                ],
                query=(
                    {"bool": {"filter": filters}}
                    if len(filters) > 0
                    else {"match_all": {}}
                ),
            )

            if len(result["hits"]["hits"]) > 0:
                prev_cursor = json.dumps(
                    {
                        "sort": first_item["sort"],
                        "order": "asc",
                    }
                )
                prev_cursor = base64.b64encode(prev_cursor.encode()).decode()

        serializer = RuntimeLogsSearchSerializer(
            dict(
                query_time_ms=query_time_ms,
                total=total,
                results=[
                    {
                        "id": hit["_id"],
                        "time": hit["_source"]["time"],
                        "level": hit["_source"]["level"],
                        "source": hit["_source"]["source"],
                        "service_id": hit["_source"]["service_id"],
                        "deployment_id": hit["_source"]["deployment_id"],
                        "content": hit["_source"]["content"]["raw"],
                        "content_text": hit["_source"]["content"]["text"],
                    }
                    for hit in hits
                ],
                next=next_cursor,
                previous=prev_cursor,
            )
        )

        print(
            f"Found {Colors.BLUE}{total}{Colors.ENDC} logs in ElasticSearch in {Colors.GREEN}{query_time_ms}ms{Colors.ENDC}"
        )
        print(f"====== END LOGS SEARCH ======")
        return serializer.data

    def count(self, index_name: str, query: dict = None) -> int:
        print(f"====== LOGS COUNT ======")
        print(f"Index: {Colors.BLUE}{index_name}{Colors.ENDC}")
        filters = self._compute_filters(query)["filters"]
        count = self.es.count(
            index=index_name,
            query=(
                {"bool": {"filter": filters}} if len(filters) > 0 else {"match_all": {}}
            ),
        )["count"]
        print(
            f"Found {Colors.BLUE}{count}{Colors.ENDC} logs in ElasticSearch index {Colors.BLUE}{index_name}{Colors.ENDC}"
        )
        print(f"====== END LOGS COUNT ======")
        return count

    def delete(self, index_name: str, query: dict = None) -> int:
        from django.conf import settings

        print(f"====== LOGS DELETE ======")
        print(f"Index: {Colors.BLUE}{index_name}{Colors.ENDC}")

        filters = self._compute_filters(query)["filters"]

        response = self.es.delete_by_query(
            index=index_name,
            query=(
                {"bool": {"filter": filters}} if len(filters) > 0 else {"match_all": {}}
            ),
            refresh=settings.TESTING,
        )
        print(
            f"Deleted {Colors.BLUE}{response['deleted']} documents{Colors.ENDC} in ElasticSearch index {Colors.BLUE}{index_name}{Colors.ENDC}"
        )
        print("====== END LOGS DELETE ======")
        return response["deleted"]

    def _compute_filters(self, query: dict = None):
        form = RuntimeLogsQuerySerializer(data=query or {})
        form.is_valid(raise_exception=True)

        search_params = form.validated_data or {}
        filters = []

        page_size = int(search_params.get("per_page", 50))
        if search_params.get("service_id"):
            filters.append({"term": {"service_id": search_params["service_id"]}})
        if search_params.get("deployment_id"):
            filters.append({"term": {"deployment_id": search_params["deployment_id"]}})
        if search_params.get("level"):
            filters.append({"terms": {"level": search_params["level"]}})
        if search_params.get("source"):
            filters.append({"terms": {"source": search_params["source"]}})
        if search_params.get("time_after") or search_params.get("time_before"):
            range_filter = {
                "range": {
                    "time": {
                        "format": "strict_date_optional_time_nanos",
                    }
                }
            }

            if search_params.get("time_after"):
                range_filter["range"]["time"]["gte"] = search_params["time_after"]
            if search_params.get("time_before"):
                range_filter["range"]["time"]["lte"] = search_params["time_before"]
            filters.append(range_filter)
        if search_params.get("query"):
            # escape `*` in the query string as it is a special character in ElasticSearch
            query = search_params["query"].replace("*", "\\*")
            filters.append(
                {"wildcard": {"content.text.keyword": {"value": f"*{query}*"}}}
            )

        search_after = None
        cursor = None

        order = "desc"
        if search_params.get("cursor"):
            cursor = base64.b64decode(search_params["cursor"]).decode()
            cursor = json.loads(cursor)
            search_after = cursor["sort"]
            order = cursor["order"]

        print(f"Params: {Colors.GREY}{search_params}{Colors.ENDC}")
        print(f"Filters: {Colors.GREY}{filters}{Colors.ENDC}")
        print(f"Cursor: {Colors.GREY}{cursor}{Colors.ENDC}")

        return {
            "filters": filters,
            "search_after": search_after,
            "order": order,
            "page_size": page_size,
        }

    def create_log_index_if_not_exists(self, index_name: str):
        if not self.es.indices.exists(index=index_name):
            self.es.indices.create(
                index=index_name,
                mappings={
                    "properties": {
                        "content": {
                            "properties": {
                                "raw": {
                                    "type": "text",
                                    "index": False,
                                },
                                "text": {
                                    "type": "text",
                                    "fields": {
                                        "keyword": {
                                            "type": "keyword",
                                            # Apache Lucene that ElasticSearch is built on has a limit of 32766 bytes for keyword fields
                                            # by default, so logs with content longer than that will be ignored for search and indexing
                                            # 32766 bytes doesn't necessarily mean 32766 characters, as some characters in UTF-8 can take up more than 1 byte
                                            # But for most cases, it should be enough
                                            # reference: https://www.elastic.co/guide/en/elasticsearch/reference/current/ignore-above.html
                                            # "ignore_above": 32766,
                                        }
                                    },
                                },
                            }
                        },
                        "deployment_id": {"type": "keyword"},
                        "level": {"type": "keyword"},
                        "source": {"type": "keyword"},
                        "service_id": {"type": "keyword"},
                        "time": {"type": "date_nanos"},
                        "created_at": {"type": "date_nanos"},
                    }
                },
            )
            print(
                f"{Colors.GREEN}Successfully created ElasticSearch index {Colors.BLUE}{index_name}{Colors.ENDC} ✨"
            )
        else:
            print(
                f"Index {Colors.BLUE}{index_name}{Colors.ENDC} already exists in ElasticSearch, skipping creation ⏭️"
            )

    def delete_index(self, index_name: str):
        print(f"Deleting ElasticSearch index {Colors.BLUE}{index_name}{Colors.ENDC}...")
        self.es.indices.delete(index=index_name)
        print(
            f"{Colors.GREEN}Successfully deleted ElasticSearch index {Colors.BLUE}{index_name}{Colors.ENDC} 🗑️"
        )
