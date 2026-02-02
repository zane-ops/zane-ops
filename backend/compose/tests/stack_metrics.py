from ..models import ComposeStackMetrics
from .fixtures import DOCKER_COMPOSE_MINIMAL, DOCKER_COMPOSE_WEB_WITH_DB
from .stacks import ComposeStackAPITestBase
from temporal.schedules import CollectComposeStacksMetricsWorkflow
from django.conf import settings
from asgiref.sync import sync_to_async
from zane_api.utils import jprint


class CollectStackMetricsTests(ComposeStackAPITestBase):
    async def test_create_metrics_schedule_when_deploying_a_stack(self):
        p, stack = await self.acreate_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_MINIMAL
        )

        self.assertIsNotNone(
            self.get_workflow_schedule_by_id(stack.metrics_schedule_id)
        )

    async def test_run_collect_stack_metrics_schedule(self):
        async with self.workflowEnvironment() as env:
            p, stack = await self.acreate_and_deploy_compose_stack(
                content=DOCKER_COMPOSE_WEB_WITH_DB
            )

            @sync_to_async
            def get_snapshot():
                return stack.snapshot

            self.assertIsNotNone(
                self.get_workflow_schedule_by_id(stack.metrics_schedule_id)
            )
            result = await env.client.execute_workflow(
                workflow=CollectComposeStacksMetricsWorkflow.run,
                arg=await get_snapshot(),
                id=stack.metrics_schedule_id,
                task_queue=settings.TEMPORALIO_MAIN_TASK_QUEUE,
                execution_timeout=settings.TEMPORALIO_WORKFLOW_EXECUTION_MAX_TIMEOUT,
            )
            jprint(result)

            self.assertEqual(
                3, await ComposeStackMetrics.objects.filter(stack=stack).acount()
            )
            self.assertIsNotNone(
                await ComposeStackMetrics.objects.filter(
                    stack=stack, service_name="web"
                ).afirst()
            )
            self.assertIsNotNone(
                await ComposeStackMetrics.objects.filter(
                    stack=stack, service_name="db"
                ).afirst()
            )
            self.assertIsNotNone(
                await ComposeStackMetrics.objects.filter(
                    stack=stack, service_name="cache"
                ).afirst()
            )
