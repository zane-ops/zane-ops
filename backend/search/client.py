from typing import Generator
from elasticsearch import Elasticsearch, helpers
from zane_api.utils import Colors


class SearchClient:
    def __init__(self, host: str):
        self.es = Elasticsearch(host, api_key="")

    def search(self, index_name: str, **kwargs):
        """
        TODO
        """
        pass

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
