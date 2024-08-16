from temporalio import workflow

from .shared import (
    HealthcheckDeploymentDetails,
)

with workflow.unsafe.imports_passed_through():
    pass


@workflow.defn(name="monitor-docker-deployment-workflow")
class MonitorDockerDeploymentWorkflow:
    @workflow.run
    async def run(self, payload: HealthcheckDeploymentDetails):
        print(f"\nRunning workflow MonitorDockerDeploymentWorkflow with {payload=}")
        pass
