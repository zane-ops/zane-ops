# management/commands/index_logs_to_meilisearch.py
from django.core.management.base import BaseCommand
from ...models import SimpleLog
import requests
import json

MEILISEARCH_URL = "http://localhost:7700"
INDEX_NAME = "logs"
BATCH_SIZE = 10000  # Number of documents per batch
MAX_DOCUMENTS = 1000000  # Limit the number of documents indexed


class Command(BaseCommand):
    help = "Index logs to Meilisearch"

    def handle(self, *args, **kwargs):
        # Ensure the index exists
        index_response = requests.post(f"{MEILISEARCH_URL}/indexes/{INDEX_NAME}")
        if index_response.status_code not in [200, 201]:
            self.stdout.write(
                self.style.WARNING(
                    f"Index already exists or failed to create: {index_response.text}"
                )
            )

        # Fetch and index logs in batches
        total_documents = 0
        while total_documents < MAX_DOCUMENTS:
            logs = SimpleLog.objects.all().values(
                "id",
                "created_at",
                "service_id",
                "deployment_id",
                "time",
                "content",
                "content_text",
                "level",
                "source",
            )[total_documents : total_documents + BATCH_SIZE]

            if not logs:
                break

            documents = [
                {
                    "id": str(log["id"]),
                    "created_at": log["created_at"].timestamp(),
                    "time": log["time"].timestamp(),
                    "service_id": log["service_id"],
                    "deployment_id": log["deployment_id"],
                    "content": str(log["content"]),
                    "content_text": log["content_text"],
                    "level": log["level"],
                    "source": log["source"],
                }
                for log in logs
            ]

            self.stdout.write(
                self.style.HTTP_INFO(
                    f"Indexing documents {total_documents}-{total_documents + BATCH_SIZE} to Meilisearch..."
                )
            )

            response = requests.post(
                f"{MEILISEARCH_URL}/indexes/{INDEX_NAME}/documents",
                json=documents,
            )

            if response.status_code in [200, 202]:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Successfully indexed {len(documents)} logs to Meilisearch."
                    )
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f"Failed to index logs: {response.text}")
                )
                break

            total_documents += len(documents)

        self.stdout.write(
            self.style.SUCCESS(
                f"Indexing completed. Total documents indexed: {total_documents}"
            )
        )
