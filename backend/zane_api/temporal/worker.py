from django.conf import settings
from temporalio.client import Client
from temporalio.service import KeepAliveConfig
from temporalio.worker import Worker

from .workflows import get_workflows_and_activities
from concurrent.futures import ThreadPoolExecutor


async def run_worker():
    print(f"Connecting worker to temporal server...🔄")
    client = await Client.connect(
        settings.TEMPORALIO_SERVER_URL,
        namespace=settings.TEMPORALIO_WORKER_NAMESPACE,
        keep_alive_config=KeepAliveConfig(timeout_millis=120_000),
    )
    print(f"worker connected ✅")
    with ThreadPoolExecutor(max_workers=10) as activity_executor:
        worker = Worker(
            client,
            task_queue=settings.TEMPORALIO_WORKER_TASK_QUEUE,
            debug_mode=True,
            **get_workflows_and_activities(),
            activity_executor=activity_executor,
        )
        print(
            f"running worker on task queue `{settings.TEMPORALIO_WORKER_TASK_QUEUE}`...🔄"
        )
        await worker.run()
