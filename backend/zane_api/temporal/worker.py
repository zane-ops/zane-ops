from django.conf import settings
from temporalio.client import Client
from temporalio.service import KeepAliveConfig
from temporalio.worker import Worker

from .activities import DockerSwarmActivities
from .workflows import CreateProjectResourcesWorkflow, RemoveProjectResourcesWorkflow


async def run_worker():
    print(f"Connecting worker to temporal server...🔄")
    client = await Client.connect(
        settings.TEMPORALIO_SERVER_URL,
        namespace="default",
        keep_alive_config=KeepAliveConfig(timeout_millis=120_000),
    )
    print(f"worker connected ✅")
    activities = DockerSwarmActivities()
    worker = Worker(
        client,
        task_queue=settings.TEMPORALIO_MAIN_TASK_QUEUE,
        workflows=[CreateProjectResourcesWorkflow, RemoveProjectResourcesWorkflow],
        activities=[
            activities.attach_network_to_proxy,
            activities.create_project_network,
            activities.unexpose_docker_service_from_http,
            activities.detach_network_from_proxy,
            activities.remove_project_network,
            activities.cleanup_docker_service_resources,
            activities.get_archived_project_services,
        ],
        debug_mode=True,
    )
    print(f"running worker...🔄")
    await worker.run()
