import asyncio

from django.core.management.base import BaseCommand

from ...temporal.worker import run_worker


class Command(BaseCommand):
    help = "Run temporal worker"

    def handle(self, *args, **options):
        asyncio.run(run_worker())
