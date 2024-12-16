# management/commands/create_quickwit_index.py
from django.core.management.base import BaseCommand
import requests
import json

QUICKWIT_API_URL = "http://localhost:7280"  # Update this to your Quickwit API URL


class Command(BaseCommand):
    help = "Create a Quickwit index for logs"

    def handle(self, *args, **kwargs):
        # Define the schema for the index
        schema = {
            "index_id": "logs",
            "version": "0.8",
            "doc_mapping": {
                "field_mappings": [
                    {
                        "name": "id",
                        "tokenizer": "raw",
                        "type": "text",
                        "fast": False,
                        "record": "basic",
                        "fieldnorms": False,
                    },
                    {
                        "name": "created_at",
                        "type": "datetime",
                        "input_formats": ["iso8601", "unix_timestamp"],
                        "fast": True,
                    },
                    {
                        "name": "time",
                        "type": "datetime",
                        "input_formats": ["iso8601", "unix_timestamp"],
                        "fast": True,
                    },
                    {
                        "name": "service_id",
                        "type": "text",
                        "fast": {"normalizer": "raw"},
                        "tokenizer": "raw",
                        "record": "basic",
                        "fieldnorms": False,
                    },
                    {
                        "name": "deployment_id",
                        "type": "text",
                        "fast": {"normalizer": "raw"},
                        "tokenizer": "raw",
                        "record": "basic",
                        "fieldnorms": False,
                    },
                    {
                        "name": "content",
                        "type": "text",
                        "fast": False,
                    },
                    {
                        "name": "content_text",
                        "type": "text",
                        "record": "position",
                        "fast": {"normalizer": "lowercase"},
                    },
                    {
                        "name": "level",
                        "type": "text",
                        "fast": {"normalizer": "raw"},
                        "tokenizer": "raw",
                        "record": "basic",
                        "fieldnorms": False,
                    },
                    {
                        "name": "source",
                        "type": "text",
                        "fast": {"normalizer": "raw"},
                        "tokenizer": "raw",
                        "record": "basic",
                        "fieldnorms": False,
                    },
                ],
                "timestamp_field": "time",
            },
            "search_settings": {"default_search_fields": ["content_text"]},
            "retention": {"period": "30 days", "schedule": "daily"},
        }

        # Send a request to create the index
        response = requests.post(f"{QUICKWIT_API_URL}/api/v1/indexes", json=schema)

        if response.status_code == 200:
            self.stdout.write(
                self.style.SUCCESS("Successfully created Quickwit index.")
            )
        else:
            self.stdout.write(
                self.style.ERROR(f"Failed to create Quickwit index: {response.json()}")
            )
