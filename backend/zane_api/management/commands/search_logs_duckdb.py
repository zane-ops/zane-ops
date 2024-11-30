# management/commands/load_and_search_logs_duckdb.py
import duckdb
from django.core.management.base import BaseCommand
from ...models import SimpleLog
from ...utils import Colors
import time
import datetime


class Command(BaseCommand):
    help = (
        "Load logs from PostgreSQL into DuckDB and perform a sample search for testing"
    )

    def handle(self, *args, **kwargs):
        with duckdb.connect("logs.db") as con:
            # Sample search query for testing
            content_search = input("Enter content to search for: ")

            time_after = datetime.datetime.fromisoformat("2024-11-26T23:00:00.000Z")
            time_before = datetime.datetime.fromisoformat("2024-11-27T22:59:59.999Z")
            search_query = f"""
            SELECT
                *
            FROM
                logs
            WHERE
                content_text ILIKE ?
                AND deployment_id = 'dpl_dkr_PsnsqZZfgu7'
            ORDER BY
                time desc,
                created_at desc
            LIMIT
                50
            """
            #             AND source = 'SERVICE'
            # AND level = 'INFO'
            # AND time BETWEEN  '{time_after.isoformat()}' AND '{time_before.isoformat()}'

            start = time.monotonic()
            results = con.execute(search_query, [f"%{content_search}%"]).fetchall()
            duration = time.monotonic() - start
            for result in results[:5]:
                self.stdout.write(
                    f"{Colors.GREY}{result[4]}{Colors.ENDC} - {result[5][:1000]}"
                )

            self.stdout.write(
                self.style.SUCCESS(
                    f"[Duckdb] Sample search completed with results in {duration*1_000:.2f}ms"
                )
            )

            start = time.monotonic()

            results = SimpleLog.objects.filter(
                content_text__icontains=content_search,
                deployment_id="dpl_dkr_PsnsqZZfgu7",
                # source="SERVICE",
                # level="INFO",
                # time__gte=time_after,
                # time__lte=time_before,
            ).order_by("-time", "-created_at")
            for i, result in enumerate(results[:50]):
                self.stdout.write(
                    f"{Colors.GREY}{result.time}{Colors.ENDC} - {str(result.content)[:1000]}"
                )
                if i == 4:
                    break

            duration = time.monotonic() - start
            self.stdout.write(
                self.style.SUCCESS(
                    f"[django ORM] Sample search completed with results in {duration*1_000:.2f}ms"
                )
            )
