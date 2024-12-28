from django.core.management.base import BaseCommand
from search.client import SearchClient
from django.conf import settings
from ...models import SimpleLog
from django.db.models import Q

BATCH_SIZE = 10_000
MAX_DOCUMENTS = 2_000_000


class Command(BaseCommand):
    help = "Index logs to Elasticsearch"

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=BATCH_SIZE,
            help="Number of logs to index in each batch",
        )
        parser.add_argument(
            "--max-documents",
            type=int,
            default=MAX_DOCUMENTS,
            help="Maximum number of logs to index",
        )

    def handle(self, *args, **options):
        total_documents_indexed = 0
        client = SearchClient(settings.ELASTICSEARCH_HOST)
        client.clear_index_data(settings.ELASTICSEARCH_LOGS_INDEX)

        max_documents = options["max_documents"]
        batch_size = options["batch_size"]

        while total_documents_indexed < max_documents:
            # Fetch logs from the database in batches
            logs = SimpleLog.objects.filter(
                Q(content__isnull=False)
                & Q(content_text__isnull=False)
                & Q(deployment_id__isnull=False)
                & Q(service_id__isnull=False),
            ).values(
                "service_id",
                "deployment_id",
                "time",
                "content",
                "content_text",
                "level",
                "source",
            )[
                total_documents_indexed : total_documents_indexed + batch_size
            ]
            if len(logs) == 0:
                break

            def documents():
                for log in logs:
                    yield {
                        "_index": settings.ELASTICSEARCH_LOGS_INDEX,
                        "service_id": log["service_id"],
                        "deployment_id": log["deployment_id"],
                        "time": log["time"].isoformat(),
                        "content": {
                            "text": log["content_text"],
                            "raw": log["content"],
                        },
                        "level": log["level"],
                        "source": log["source"],
                    }

            client.bulk_insert(documents())
            total_documents_indexed += len(logs)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Indexed {len(logs)} logs to ElasticSearch. Total indexed: {total_documents_indexed}"
                )
            )

        self.stdout.write(
            self.style.HTTP_SUCCESS(f"=========  Finished indexing logs =========")
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Total sent to ElasticSearch: {total_documents_indexed}"
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Total logs indexed in ElasticSearch: {client.count(settings.ELASTICSEARCH_LOGS_INDEX)}"
            )
        )
