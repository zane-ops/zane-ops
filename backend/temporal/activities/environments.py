from temporalio import activity, workflow
from ..shared import EnvironmentDetails

with workflow.unsafe.imports_passed_through():
    from zane_api.models import Environment
    from asgiref.sync import sync_to_async


@activity.defn
async def delete_env_resources(payload: EnvironmentDetails):
    try:
        environment = (
            await Environment.objects.filter(id=payload.id)
            .select_related("preview_metadata")
            .aget()
        )
    except Environment.DoesNotExist:
        pass  # the environment may have already been deleted
    else:
        await sync_to_async(environment.delete_resources)()
        await environment.adelete()
