from django.core.management.base import BaseCommand
import requests


class Command(BaseCommand):
    help = "Create a Meilisearch index for logs"

    def handle(self, *args, **kwargs):
        MEILISEARCH_URL = "http://localhost:7700"
        INDEX_NAME = "logs"

        # Define index settings with columns and facets
        settings = {
            "uid": INDEX_NAME,
            "primaryKey": "id",
        }

        # Create the index
        response = requests.post(f"{MEILISEARCH_URL}/indexes", json=settings)

        if response.status_code < 400:
            self.stdout.write(
                self.style.SUCCESS(f"Successfully created index: {INDEX_NAME}")
            )

            # Set searchable attributes and facets
            config_response = requests.patch(
                f"{MEILISEARCH_URL}/indexes/{INDEX_NAME}/settings",
                json={
                    "searchableAttributes": ["content_text"],
                    "filterableAttributes": [
                        "service_id",
                        "deployment_id",
                        "level",
                        "source",
                        "time",
                    ],
                    "sortableAttributes": ["created_at", "time"],
                    "rankingRules": [
                        "exactness",
                        # "words",
                        # "proximity",
                        # "typo",
                    ],
                    "typoTolerance": {"enabled": False},
                },
            )
            config_response = requests.put(
                f"{MEILISEARCH_URL}/indexes/{INDEX_NAME}/settings/non-separator-tokens",
                json=[
                    "-",
                    "_",
                    "'",
                    ":",
                    "/",
                    "\\",
                    "@",
                    "&",
                    '"',
                    "+",
                    "~",
                    "=",
                    "^",
                    "*",
                    ".",
                    ";",
                    ",",
                    "!",
                    "?",
                    "(",
                    ")",
                    "[",
                    "]",
                    "{",
                    "$",
                    "#",
                    "}",
                    "|",
                ],
            )

            if config_response.status_code < 400:
                self.stdout.write(
                    self.style.SUCCESS("Successfully configured index settings.")
                )
            else:
                self.stdout.write(
                    self.style.ERROR(
                        f"Failed to configure index settings: {config_response.json()}"
                    )
                )
        else:
            print(f"{response.status_code=}")
            self.stdout.write(
                self.style.ERROR(f"Failed to create index: {response.json()}")
            )
