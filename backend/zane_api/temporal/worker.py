from django.conf import settings
from temporalio.client import Client
from temporalio.service import KeepAliveConfig
from temporalio.worker import Worker

from .activities import acreate_project_resources
from .workflows import CreateProjectResourcesWorkflow


async def run_worker():
    print(f"Connecting worker to temporal server...🔄")
    client = await Client.connect(
        settings.TEMPORALIO_SERVER_URL,
        namespace="default",
        keep_alive_config=KeepAliveConfig(timeout_millis=120_000),
    )
    print(f"worker connected ✅")
    worker = Worker(
        client,
        task_queue=settings.TEMPORALIO_MAIN_TASK_QUEUE,
        workflows=[CreateProjectResourcesWorkflow],
        activities=[acreate_project_resources],
        debug_mode=True,
    )
    print(f"running worker...🔄")
    await worker.run()
