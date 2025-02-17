from django.conf import settings

from .base import AuthAPITestCase
from ..dtos import HealthCheckDto
from ..models import (
    DockerDeployment,
    HealthCheck,
)
from ..temporal import (
    MonitorDockerDeploymentWorkflow,
    HealthcheckDeploymentDetails,
    SimpleDeploymentDetails,
)


class DockerServiceMonitorTests(AuthAPITestCase):
    async def test_normal_deployment_flow(self):
        async with self.workflowEnvironment() as env:
            p, service = await self.acreate_and_deploy_redis_docker_service()
            latest_deployment: DockerDeployment = await service.alatest_production_deployment  # type: ignore
            self.assertEqual(
                DockerDeployment.DeploymentStatus.HEALTHY,
                latest_deployment.status,
            )

            healthcheck = latest_deployment.service.healthcheck
            healthcheck_details = HealthcheckDeploymentDetails(
                deployment=SimpleDeploymentDetails(
                    hash=latest_deployment.hash,
                    service_id=latest_deployment.service.id,
                    project_id=latest_deployment.service.project_id,
                ),
                healthcheck=(
                    HealthCheckDto.from_dict(
                        dict(
                            type=healthcheck.type,
                            value=healthcheck.value,
                            timeout_seconds=healthcheck.timeout_seconds,
                            interval_seconds=healthcheck.interval_seconds,
                            id=healthcheck.id,
                        )
                    )
                    if healthcheck is not None
                    else None
                ),
            )
            await env.client.execute_workflow(
                workflow=MonitorDockerDeploymentWorkflow.run,
                arg=healthcheck_details,
                id=latest_deployment.monitor_schedule_id,
                task_queue=settings.TEMPORALIO_MAIN_TASK_QUEUE,
                execution_timeout=settings.TEMPORALIO_WORKFLOW_EXECUTION_MAX_TIMEOUT,
            )
            latest_deployment = await service.alatest_production_deployment  # type: ignore
            self.assertEqual(
                DockerDeployment.DeploymentStatus.HEALTHY,
                latest_deployment.status,
            )

    async def test_restart_is_set_after_multiple_tasks_deployments(self):
        async with self.workflowEnvironment() as env:
            p, service = await self.acreate_and_deploy_redis_docker_service()
            latest_deployment: DockerDeployment = await service.alatest_production_deployment  # type: ignore
            self.assertEqual(
                DockerDeployment.DeploymentStatus.HEALTHY,
                latest_deployment.status,
            )

            class FakeService:
                @staticmethod
                def tasks(*args, **kwargs):
                    return [
                        {
                            "ID": "8qx04v72iovlv7xzjvsj2ngdkg",
                            "Version": {"Index": 15078},
                            "CreatedAt": "2024-04-25T20:11:32.736667861Z",
                            "UpdatedAt": "2024-04-25T20:11:43.065656097Z",
                            "Status": {
                                "Timestamp": "2024-04-25T20:11:42.770670997Z",
                                "State": "shutdown",
                                "Message": "started",
                                "Err": "task: non-zero exit (127)",
                                "ContainerStatus": {
                                    "ExitCode": 127,
                                },
                            },
                            "DesiredState": "shutdown",
                        },
                        {
                            "ID": "8qx04v72iovlv7xzjvsj2ngdk",
                            "Version": {"Index": 15079},
                            "CreatedAt": "2024-04-25T20:11:32.736667861Z",
                            "UpdatedAt": "2024-04-25T20:11:43.065656097Z",
                            "Status": {
                                "Timestamp": "2024-04-25T20:11:42.770670997Z",
                                "State": "starting",
                                "Message": "started",
                                # "Err": "task: non-zero exit (127)",
                                "ContainerStatus": {
                                    "ExitCode": 0,
                                },
                            },
                            "DesiredState": "starting",
                        },
                    ]

            self.fake_docker_client.services.get = lambda _id: FakeService()

            healthcheck: HealthCheck | None = latest_deployment.service.healthcheck
            healthcheck_details = HealthcheckDeploymentDetails(
                deployment=SimpleDeploymentDetails(
                    hash=latest_deployment.hash,
                    service_id=latest_deployment.service.id,
                    project_id=latest_deployment.service.project_id,
                ),
                healthcheck=(
                    HealthCheckDto.from_dict(
                        dict(
                            type=healthcheck.type,
                            value=healthcheck.value,
                            timeout_seconds=healthcheck.timeout_seconds,
                            interval_seconds=healthcheck.interval_seconds,
                            id=healthcheck.id,
                        )
                    )
                    if healthcheck is not None
                    else None
                ),
            )
            await env.client.execute_workflow(
                workflow=MonitorDockerDeploymentWorkflow.run,
                arg=healthcheck_details,
                id=latest_deployment.monitor_schedule_id,
                task_queue=settings.TEMPORALIO_MAIN_TASK_QUEUE,
                execution_timeout=settings.TEMPORALIO_WORKFLOW_EXECUTION_MAX_TIMEOUT,
            )
            latest_deployment = await service.alatest_production_deployment  # type: ignore
            self.assertEqual(
                DockerDeployment.DeploymentStatus.RESTARTING,
                latest_deployment.status,
            )

    async def test_succesful_restart_deployment_flow(self):
        async with self.workflowEnvironment() as env:
            p, service = await self.acreate_and_deploy_redis_docker_service()
            latest_deployment: DockerDeployment = await service.alatest_production_deployment  # type: ignore
            self.assertEqual(
                DockerDeployment.DeploymentStatus.HEALTHY,
                latest_deployment.status,
            )

            class FakeService:
                @staticmethod
                def tasks(*args, **kwargs):
                    return [
                        {
                            "ID": "8qx04v72iovlv7xzjvsj2ngdkg",
                            "Version": {"Index": 15078},
                            "CreatedAt": "2024-04-25T20:11:32.736667861Z",
                            "UpdatedAt": "2024-04-25T20:11:43.065656097Z",
                            "Status": {
                                "Timestamp": "2024-04-25T20:11:42.770670997Z",
                                "State": "shutdown",
                                "Message": "started",
                                "Err": "task: non-zero exit (127)",
                                "ContainerStatus": {
                                    "ExitCode": 127,
                                },
                            },
                            "DesiredState": "shutdown",
                        },
                        {
                            "ID": "8qx04v72iovlv7xzjvsj2ngdk",
                            "Version": {"Index": 15079},
                            "CreatedAt": "2024-04-25T20:11:32.736667861Z",
                            "UpdatedAt": "2024-04-25T20:11:43.065656097Z",
                            "Status": {
                                "Timestamp": "2024-04-25T20:11:42.770670997Z",
                                "State": "running",
                                "Message": "started",
                                # "Err": "task: non-zero exit (127)",
                                "ContainerStatus": {
                                    "ExitCode": 0,
                                },
                            },
                            "DesiredState": "running",
                        },
                    ]

            self.fake_docker_client.services.get = lambda _id: FakeService()

            healthcheck: HealthCheck | None = latest_deployment.service.healthcheck
            healthcheck_details = HealthcheckDeploymentDetails(
                deployment=SimpleDeploymentDetails(
                    hash=latest_deployment.hash,
                    service_id=latest_deployment.service.id,
                    project_id=latest_deployment.service.project_id,
                ),
                healthcheck=(
                    HealthCheckDto.from_dict(
                        dict(
                            type=healthcheck.type,
                            value=healthcheck.value,
                            timeout_seconds=healthcheck.timeout_seconds,
                            interval_seconds=healthcheck.interval_seconds,
                            id=healthcheck.id,
                        )
                    )
                    if healthcheck is not None
                    else None
                ),
            )
            await env.client.execute_workflow(
                workflow=MonitorDockerDeploymentWorkflow.run,
                arg=healthcheck_details,
                id=latest_deployment.monitor_schedule_id,
                task_queue=settings.TEMPORALIO_MAIN_TASK_QUEUE,
                execution_timeout=settings.TEMPORALIO_WORKFLOW_EXECUTION_MAX_TIMEOUT,
            )
            latest_deployment = await service.alatest_production_deployment  # type: ignore
            self.assertEqual(
                DockerDeployment.DeploymentStatus.HEALTHY,
                latest_deployment.status,
            )

    async def test_unsuccesful_restart_deployment_flow(self):
        async with self.workflowEnvironment() as env:
            p, service = await self.acreate_and_deploy_redis_docker_service()
            latest_deployment: DockerDeployment = await service.alatest_production_deployment  # type: ignore
            self.assertEqual(
                DockerDeployment.DeploymentStatus.HEALTHY,
                latest_deployment.status,
            )

            class FakeService:
                @staticmethod
                def tasks(*args, **kwargs):
                    return [
                        {
                            "ID": "8qx04v72iovlv7xzjvsj2ngdk",
                            "Version": {"Index": 15078},
                            "CreatedAt": "2024-04-25T20:11:32.736667861Z",
                            "UpdatedAt": "2024-04-25T20:11:43.065656097Z",
                            "Status": {
                                "Timestamp": "2024-04-25T20:11:42.770670997Z",
                                "State": "failed",
                                "Message": "started",
                                "Err": "task: non-zero exit (127)",
                                "ContainerStatus": {
                                    "ContainerID": "a6e983977676b708ed0201c91c4fa3c6fbc4c1d43f7520327db8efc5ba8b76f0",
                                    "PID": 0,
                                    "ExitCode": 127,
                                },
                                "PortStatus": {},
                            },
                            "DesiredState": "shutdown",
                        },
                        {
                            "ID": "jumpidf77nnc9u24dn2t0t8gk",
                            "Version": {"Index": 15070},
                            "CreatedAt": "2024-04-25T20:11:21.303508844Z",
                            "UpdatedAt": "2024-04-25T20:11:32.93669947Z",
                            "Status": {
                                "Timestamp": "2024-04-25T20:11:32.642315167Z",
                                "State": "failed",
                                "Message": "started",
                                "Err": "task: non-zero exit (127)",
                                "ContainerStatus": {
                                    "ContainerID": "407c4b40d621b127a1cac498d066587522f4ddcca1ec01992dbf94f49c6092fc",
                                    "PID": 0,
                                    "ExitCode": 127,
                                },
                                "PortStatus": {},
                            },
                            "DesiredState": "shutdown",
                        },
                        {
                            "ID": "wqnwod7cacovpscsp3n6vsgmc",
                            "Version": {"Index": 15091},
                            "CreatedAt": "2024-04-25T20:11:52.686304192Z",
                            "UpdatedAt": "2024-04-25T20:12:02.693438335Z",
                            "Status": {
                                "Timestamp": "2024-04-25T20:12:02.415795453Z",
                                "State": "failed",
                                "Message": "started",
                                "Err": "task: non-zero exit (127)",
                                "ContainerStatus": {
                                    "ContainerID": "edd2aa5d80747f860b1cee700a1028e7000970f05a8fe9784fa0f81c460459ac",
                                    "PID": 0,
                                    "ExitCode": 127,
                                },
                                "PortStatus": {},
                            },
                            "DesiredState": "shutdown",
                        },
                        {
                            "ID": "wwkdns3g7fsyq37hwe5cj7spl",
                            "Version": {"Index": 15086},
                            "CreatedAt": "2024-04-25T20:11:42.863807131Z",
                            "UpdatedAt": "2024-04-25T20:11:52.887691861Z",
                            "Status": {
                                "Timestamp": "2024-04-25T20:11:52.620438735Z",
                                "State": "failed",
                                "Message": "started",
                                "Err": "task: non-zero exit (127)",
                                "ContainerStatus": {
                                    "ContainerID": "f45b1785bca08314c9b6af63bdf8080aa79d60a427315d9fe96ba8928d1d1d54",
                                    "PID": 0,
                                    "ExitCode": 127,
                                },
                                "PortStatus": {},
                            },
                            "DesiredState": "shutdown",
                        },
                    ]

            self.fake_docker_client.services.get = lambda _id: FakeService()

            healthcheck: HealthCheck | None = latest_deployment.service.healthcheck
            healthcheck_details = HealthcheckDeploymentDetails(
                deployment=SimpleDeploymentDetails(
                    hash=latest_deployment.hash,
                    service_id=latest_deployment.service.id,
                    project_id=latest_deployment.service.project_id,
                ),
                healthcheck=(
                    HealthCheckDto.from_dict(
                        dict(
                            type=healthcheck.type,
                            value=healthcheck.value,
                            timeout_seconds=healthcheck.timeout_seconds,
                            interval_seconds=healthcheck.interval_seconds,
                            id=healthcheck.id,
                        )
                    )
                    if healthcheck is not None
                    else None
                ),
            )
            await env.client.execute_workflow(
                workflow=MonitorDockerDeploymentWorkflow.run,
                arg=healthcheck_details,
                id=latest_deployment.monitor_schedule_id,
                task_queue=settings.TEMPORALIO_MAIN_TASK_QUEUE,
                execution_timeout=settings.TEMPORALIO_WORKFLOW_EXECUTION_MAX_TIMEOUT,
            )
            latest_deployment = await service.alatest_production_deployment  # type: ignore
            self.assertEqual(
                DockerDeployment.DeploymentStatus.UNHEALTHY,
                latest_deployment.status,
            )

    async def test_service_fail_outside_of_zane_control(self):
        async with self.workflowEnvironment() as env:
            p, service = await self.acreate_and_deploy_redis_docker_service()
            latest_deployment: DockerDeployment = await service.alatest_production_deployment  # type: ignore
            self.assertEqual(
                DockerDeployment.DeploymentStatus.HEALTHY,
                latest_deployment.status,
            )

            class FakeService:
                @staticmethod
                def tasks(*args, **kwargs):
                    return []

            self.fake_docker_client.services.get = lambda _id: FakeService()

            healthcheck: HealthCheck | None = latest_deployment.service.healthcheck
            healthcheck_details = HealthcheckDeploymentDetails(
                deployment=SimpleDeploymentDetails(
                    hash=latest_deployment.hash,
                    service_id=latest_deployment.service.id,
                    project_id=latest_deployment.service.project_id,
                ),
                healthcheck=(
                    HealthCheckDto.from_dict(
                        dict(
                            type=healthcheck.type,
                            value=healthcheck.value,
                            timeout_seconds=healthcheck.timeout_seconds,
                            interval_seconds=healthcheck.interval_seconds,
                            id=healthcheck.id,
                        )
                    )
                    if healthcheck is not None
                    else None
                ),
            )
            await env.client.execute_workflow(
                workflow=MonitorDockerDeploymentWorkflow.run,
                arg=healthcheck_details,
                id=latest_deployment.monitor_schedule_id,
                task_queue=settings.TEMPORALIO_MAIN_TASK_QUEUE,
                execution_timeout=settings.TEMPORALIO_WORKFLOW_EXECUTION_MAX_TIMEOUT,
            )
            latest_deployment = await service.alatest_production_deployment  # type: ignore
            self.assertEqual(
                DockerDeployment.DeploymentStatus.UNHEALTHY,
                latest_deployment.status,
            )
