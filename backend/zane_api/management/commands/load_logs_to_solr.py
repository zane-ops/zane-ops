# management/commands/load_logs_to_solr.py
import requests
from django.core.management.base import BaseCommand
from ...models import SimpleLog
from rest_framework import status


class Command(BaseCommand):
    help = "Load logs from PostgreSQL into Solr in chunks"

    def handle(self, *args, **kwargs):
        # self.stdout.write(
        #     self.style.HTTP_INFO(f"Clearing the logs collection in solr...")
        # )
        # response = requests.post(
        #     "http://localhost:8983/solr/logs/update",
        #     headers={"Content-Type": "application/json"},
        #     json={"delete": {"query": "*:*"}},
        # )

        # Extract logs from PostgreSQL using Django ORM
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
        )[:199_999]

        # Load logs in chunks
        chunk_size = 1_000
        for i in range(0, len(logs), chunk_size):
            chunk = [
                {
                    "created_at": log["created_at"].isoformat(),
                    "service_id": log["service_id"],
                    "deployment_id": log["deployment_id"],
                    "time": log["time"].isoformat(),
                    "content": log["content"],
                    "content_text": log["content_text"],
                    "level": log["level"],
                    "source": log["source"],
                    "backend_id": str(log["id"]),
                }
                for log in logs[i : i + chunk_size]
            ]
            self.stdout.write(
                self.style.HTTP_INFO(f"Loading chunk starting at {i} to solr")
            )
            response = requests.post(
                "http://localhost:8983/solr/logs/update/json/docs",
                json=chunk,
                headers={"Content-Type": "application/json"},
            )
            if response.status_code == status.HTTP_200_OK:
                self.stdout.write(
                    self.style.SUCCESS(f"Chunk starting at {i} loaded successfully")
                )
            else:
                self.stdout.write(
                    self.style.ERROR(
                        f"Error loading chunk starting at {i}: {response.text}"
                    )
                )

        # Commit changes to make sure data is searchable
        self.stdout.write(self.style.HTTP_INFO(f"Commiting the changes to solr..."))
        requests.get("http://localhost:8983/solr/logs/update?commit=true")
        self.stdout.write(self.style.SUCCESS("Logs successfully loaded into Solr"))
