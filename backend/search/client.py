from typing import Any, Dict, Generator, Literal, Optional
from elasticsearch import Elasticsearch, helpers
from zane_api.utils import Colors
from dataclasses import dataclass


@dataclass
class SearchQuery:
    deployment_id: str
    level: str
    source: str
    query: str
    cursor: Optional[str] = None


class RuntimeLogLevel:
    ERROR = "ERROR"
    INFO = "INFO"


class RuntimeLogSource:
    SYSTEM = "SYSTEM"
    PROXY = "PROXY"
    SERVICE = "SERVICE"


@dataclass
class RuntimeLogDto:
    id: str
    created_at: str
    time: str
    level: Literal["ERROR", "INFO"]
    source: Literal["SYSTEM", "PROXY", "SERVICE"]
    service_id: Optional[str] = None
    deployment_id: Optional[str] = None
    content: Optional[str] = None
    content_text: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        return cls(**data)


class SearchClient:
    """
    TODO :
    - limit the system logs to less than 30k characters
    - we might need to explore breaking service logs into pieces if they exceed the limit when indexing
    - add retention policy for logs in ElasticSearch to 30 days max :
        - look into index lifecycle management and rollover indices
        - delete log cleanup temporalio job
    """

    def __init__(self, host: str):
        self.es = Elasticsearch(host, api_key="")

    def search(self, index_name: str, query: SearchQuery):
        """
        TODO :
          - Run a parallel search with an exact search and a full text search
          - the exact search should be scored higher than the full text search so that the exact search results are shown first : https://www.elastic.co/guide/en/elasticsearch/reference/current/sort-search-results.html
          - look into cursor pagination if it supports both forward and backward pagination : https://www.elastic.co/guide/en/elasticsearch/reference/current/paginate-search-results.html
        """
        # self.es.search(
        #     index=index_name,
        #     size=50,
        #     sort=[
        #         {"time": {"format": "strict_date_optional_time_nanos", "order": "desc"}}
        #     ],
        #     query={
        #         "bool": {
        #             "filter": [
        #                 {"term": {"deployment_id": "dpl_dkr_fDFBezn86yr"}},
        #                 {"term": {"level": "ERROR"}},
        #                 {"term": {"source": "SERVICE"}},
        #                 {"wildcard": {"content.text.keyword": {"value": f"*{''}*"}}},
        #             ]
        #         }
        #     },
        # )
        raise NotImplementedError("search method not implemented yet")

    def count(self, index_name: str):
        return self.es.count(index=index_name)["count"]

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
                        "time": {"type": "date"},
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

    def bulk_insert(self, index_name: str, docs: list | Generator):
        print(f"Inserting documents in {Colors.BLUE}{index_name}{Colors.ENDC}...")
        helpers.bulk(
            self.es,
            docs,
        )
        print(
            f"{Colors.GREEN}Successfully indexed all documents in {Colors.BLUE}{index_name}{Colors.ENDC} 🗂️"
        )

    def clear_index_data(self, index_name: str):
        print(
            f"Clearing data in ElasticSearch index {Colors.BLUE}{index_name}{Colors.ENDC}..."
        )
        self.es.delete_by_query(index=index_name, body={"query": {"match_all": {}}})
        print(
            f"{Colors.GREEN}Successfully cleared data in ElasticSearch index {Colors.BLUE}{index_name}{Colors.ENDC} 🗑️"
        )

    def delete_index(self, index_name: str):
        print(f"Deleting ElasticSearch index {Colors.BLUE}{index_name}{Colors.ENDC}...")
        self.es.indices.delete(index=index_name)
        print(
            f"{Colors.GREEN}Successfully deleted ElasticSearch index {Colors.BLUE}{index_name}{Colors.ENDC} 🗑️"
        )
