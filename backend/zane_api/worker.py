from django.conf import settings
from temporalio.client import Client
from temporalio.service import KeepAliveConfig
from temporalio.worker import Worker

from .activities import greet, say_goodbye, get_project
from .workflows import HelloWorkflow, GetProjectWorkflow


async def run_worker():
    print(f"running main()...")
    client = await Client.connect(
        settings.TEMPORALIO_SERVER_URL,
        namespace="default",
        keep_alive_config=KeepAliveConfig(timeout_millis=120_000),
    )
    worker = Worker(
        client,
        task_queue=settings.TEMPORALIO_MAIN_TASK_QUEUE,
        workflows=[HelloWorkflow, GetProjectWorkflow],
        activities=[greet, say_goodbye, get_project],
        debug_mode=True,
    )
    await worker.run()
