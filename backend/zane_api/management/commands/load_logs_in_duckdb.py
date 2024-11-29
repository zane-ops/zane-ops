# management/commands/load_and_search_logs_duckdb.py
import duckdb
from django.core.management.base import BaseCommand
from ...models import SimpleLog
import time
import pandas as pd


class Command(BaseCommand):
    help = (
        "Load logs from PostgreSQL into DuckDB and perform a sample search for testing"
    )

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.HTTP_INFO("Fetching logs from database..."))
        start = time.monotonic()
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
        )
        duration = time.monotonic() - start
        self.stdout.write(
            self.style.SUCCESS(f"Fetched DB logs in {duration*1_000:.2f}ms")
        )

        # Connect to a persistent DuckDB database
        con = duckdb.connect("logs.db")
        con.execute("CREATE TYPE log_level AS ENUM ('ERROR', 'INFO');")
        con.execute("CREATE TYPE log_source AS ENUM ('SYSTEM', 'PROXY', 'SERVICE');")
        con.execute(
            "CREATE TABLE IF NOT EXISTS logs ("
            + "   id UUID, "
            + "   created_at TIMESTAMP,"
            + "   service_id TEXT,"
            + "   deployment_id TEXT,"
            + "   time TIMESTAMP,"
            + "   content TEXT,"
            + "   content_text TEXT,"
            + "   level log_level,"
            + "  source log_source"
            + ")"
        )

        # Create indexes for faster searching
        con.execute("CREATE INDEX IF NOT EXISTS idx_service_id ON logs (service_id)")
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_deployment_id ON logs (deployment_id)"
        )
        con.execute("CREATE INDEX IF NOT EXISTS idx_level ON logs (level)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_source ON logs (source)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON logs (created_at)")
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_content_text ON logs (content_text)"
        )

        # Clear previous data and insert new data
        self.stdout.write(
            self.style.HTTP_INFO(f"Loading {len(logs)} logs in duckDB...")
        )
        start = time.monotonic()
        df = pd.DataFrame.from_records(logs)
        con.execute("INSERT INTO logs SELECT * FROM df")

        duration = time.monotonic() - start
        self.stdout.write(
            self.style.SUCCESS(
                f"Logs successfully loaded into DuckDB in {duration*1_000:.2f}ms"
            )
        )
