# management/commands/index_logs_to_quickwit.py
from django.core.management.base import BaseCommand
from ...models import SimpleLog
import requests
import json

QUICKWIT_API_URL = "http://localhost:7280"  # Update this to your Quickwit API URL
BATCH_SIZE = 10_000
MAX_DOCUMENTS = 1000000


class Command(BaseCommand):
    help = "Index logs to Quickwit"

    def handle(self, *args, **kwargs):
        total_documents_indexed = 0

        while total_documents_indexed < MAX_DOCUMENTS:
            # Fetch logs from the database in batches
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
            )[total_documents_indexed : total_documents_indexed + BATCH_SIZE]

            documents = [
                {
                    "id": str(log["id"]),
                    "created_at": log["created_at"].isoformat(),
                    "time": log["time"].isoformat(),
                    "service_id": log["service_id"],
                    "deployment_id": log["deployment_id"],
                    "content": str(log["content"]),
                    "content_text": log["content_text"],
                    "level": log["level"],
                    "source": log["source"],
                }
                for log in logs
            ]

            if not documents:
                break

            # Upload documents to Quickwit
            response = requests.post(
                f"{QUICKWIT_API_URL}/api/v1/logs/ingest?commit=force",
                headers={"Content-Type": "application/json"},
                data="\n".join(json.dumps(doc) for doc in documents),
            )

            if response.status_code in [200, 202]:
                total_documents_indexed += len(documents)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Indexed {len(documents)} logs to Quickwit. Total indexed: {total_documents_indexed}"
                    )
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f"Failed to index logs: {response.json()}")
                )
                break

        self.stdout.write(
            self.style.SUCCESS(
                f"Finished indexing logs. Total indexed: {total_documents_indexed}"
            )
        )
