from django.conf import settings
from temporalio.client import Client
from temporalio.service import KeepAliveConfig
from temporalio.worker import (
    Worker,
    ActivityInboundInterceptor,
    Interceptor,
    ExecuteActivityInput,
)
from temporalio import workflow

from .workflows import get_workflows_and_activities


with workflow.unsafe.imports_passed_through():
    from django import db
    from asgiref.sync import sync_to_async


async def close_old_db_connections():
    """
    This function closes all unusable db connections in the main thread and the async thread
    Closing it in the main thread doesn't seem to be enough, so we also need to do it in async
    Copied from here: https://github.com/Bogdanp/django_dramatiq/issues/106#issuecomment-907781038
    """
    # Remove dead non async connections
    db.close_old_connections()
    # Remove dead async connections
    await sync_to_async(db.close_old_connections)()


class MainActivityInterceptor(ActivityInboundInterceptor):
    async def execute_activity(self, input: ExecuteActivityInput):
        result = None
        try:
            result = await super().execute_activity(input)
        except (db.utils.InterfaceError, db.utils.OperationalError):
            print("=== Closing dead DB connections before retry ===")
            await close_old_db_connections()
            result = await super().execute_activity(input)
        finally:
            print("=== Closing dead DB connections after activity execution ===")
            await close_old_db_connections()
        return result


class MainInterceptor(Interceptor):
    def intercept_activity(
        self, next: ActivityInboundInterceptor
    ) -> ActivityInboundInterceptor:
        return MainActivityInterceptor(next)

    def workflow_interceptor_class(self, input):
        return None


async def run_worker():
    print(f"Connecting worker to temporal server...🔄")
    client = await Client.connect(
        settings.TEMPORALIO_SERVER_URL,
        namespace=settings.TEMPORALIO_WORKER_NAMESPACE,
    )
    print(f"worker connected ✅")
    worker = Worker(
        client,
        task_queue=settings.TEMPORALIO_WORKER_TASK_QUEUE,
        debug_mode=True,
        **get_workflows_and_activities(),
        interceptors=[MainInterceptor()],
    )
    print(
        f"running worker on task queue `{settings.TEMPORALIO_WORKER_TASK_QUEUE}`...🔄"
    )
    await worker.run()
