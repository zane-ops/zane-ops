# management/commands/apply_schema_to_solr.py
import requests
from django.core.management.base import BaseCommand
from rest_framework import status


class Command(BaseCommand):
    help = "Apply the schema for the logs core in Solr"

    def handle(self, *args, **kwargs):
        solr_url = "http://localhost:8983/solr/logs/schema"
        fields = [
            {"name": "backend_id", "type": "string", "stored": True, "indexed": True},
            {"name": "created_at", "type": "pdate", "stored": True, "indexed": True},
            {"name": "service_id", "type": "string", "stored": True, "indexed": True},
            {
                "name": "deployment_id",
                "type": "string",
                "stored": True,
                "indexed": True,
            },
            {"name": "time", "type": "pdate", "stored": True, "indexed": True},
            {
                "name": "content",
                "type": "text_general",
                "stored": True,
                "indexed": False,
            },
            {
                "name": "content_text",
                "type": "text_general",
                "stored": True,
                "indexed": True,
            },
            {"name": "level", "type": "string", "stored": True, "indexed": True},
            {"name": "source", "type": "string", "stored": True, "indexed": True},
        ]

        headers = {"Content-Type": "application/json"}
        data = {"add-field": fields}
        self.stdout.write(self.style.HTTP_INFO("Applying Solr schema..."))
        response = requests.post(solr_url, headers=headers, json=data)
        if response.status_code == status.HTTP_200_OK:
            self.stdout.write(self.style.SUCCESS(f"All fields added successfully"))
        elif response.status_code == status.HTTP_400_BAD_REQUEST:
            self.stdout.write(self.style.WARNING(f"Fields already exist"))
            return
        else:
            raise Exception(f"Failed to add fields: {response.text}")

        self.stdout.write(self.style.HTTP_INFO("Committing changes to solr..."))
        # Commit schema changes
        commit_url = "http://localhost:8983/solr/logs/update?commit=true"
        response = requests.get(commit_url)
        if response.status_code == status.HTTP_200_OK:
            self.stdout.write(
                self.style.SUCCESS("Schema changes committed successfully")
            )
        else:
            self.stdout.write(
                self.style.ERROR(f"Failed to commit schema changes: {response.text}")
            )
