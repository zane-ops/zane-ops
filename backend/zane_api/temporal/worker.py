from django.conf import settings
from temporalio.client import Client
from temporalio.service import KeepAliveConfig
from temporalio.worker import Worker

from .workflows import get_workflows_and_activities


async def run_worker():
    print(f"Connecting worker to temporal server...🔄")
    client = await Client.connect(
        settings.TEMPORALIO_SERVER_URL,
        namespace=settings.TEMPORALIO_WORKER_NAMESPACE,
        keep_alive_config=KeepAliveConfig(timeout_millis=120_000),
    )
    print(f"worker connected ✅")
    worker = Worker(
        client,
        task_queue=settings.TEMPORALIO_MAIN_TASK_QUEUE,
        debug_mode=True,
        **get_workflows_and_activities(),
    )
    print(f"running worker...🔄")
    await worker.run()
