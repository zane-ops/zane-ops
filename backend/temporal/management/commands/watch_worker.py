import asyncio
import shlex

from django.core.management.base import BaseCommand

from watchdog.events import (
    FileSystemEvent,
    FileSystemEventHandler,
    FileOpenedEvent,
    FileClosedEvent,
)
from watchdog.observers.polling import PollingObserver
from zane_api.process import AyncSubProcessRunner

# Source - https://stackoverflow.com/a/78227581
# Posted by Marquinho Peli
# Retrieved 2026-11-09, License - CC BY-SA 4.0

import functools
from threading import Timer


def debounce(timeout: float):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            wrapper.func.cancel()  # type: ignore
            wrapper.func = Timer(timeout, func, args, kwargs)  # type: ignore
            wrapper.func.start()  # type: ignore

        wrapper.func = Timer(timeout, lambda: None)  # type: ignore
        return wrapper

    return decorator


class MyEventHandler(FileSystemEventHandler):
    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        super().__init__()
        self.loop = loop
        self.cancel_event = asyncio.Event()
        self.task = self.loop.create_task(self.run_worker_script())

    @debounce(timeout=0.3)
    def restart(self) -> None:
        # Runs inside the event loop thread
        if self.task and not self.task.done():
            self.cancel_event.set()
            self.task.cancel()
        self.cancel_event = asyncio.Event()
        self.task = self.loop.create_task(self.run_worker_script())

    async def run_worker_script(self):
        cmd = ["/app/.venv/bin/python", "/code/manage.py", "run_worker"]
        runner = AyncSubProcessRunner(
            command=shlex.join(cmd),
            cancel_event=self.cancel_event,
            operation_name="run worker",
        )
        await runner.run()

    def on_any_event(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return  # ignore directory events
        if not isinstance(event, (FileClosedEvent, FileOpenedEvent)):
            self.loop.call_soon_threadsafe(self.restart)


class Command(BaseCommand):
    help = "Run temporal worker (watch)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--watch",
            required=True,
            help="Path to watch",
        )

    def handle(self, *args, **options):
        asyncio.run(self.watch_worker(options["watch"]))

    async def watch_worker(self, path: str):
        event_handler = MyEventHandler(asyncio.get_event_loop())
        observer = PollingObserver(timeout=1)
        observer.schedule(
            event_handler,
            path,
            recursive=True,
        )

        observer.start()
        try:
            await asyncio.Event().wait()
        finally:
            print("🔄 Stopping file watchers...")
            observer.stop()
            observer.join()
            print("✅ Stopped file watchers")
