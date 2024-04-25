import json
import time
from dataclasses import dataclass
from enum import Enum

import docker.errors


# from docker.types import EndpointSpec, RestartPolicy, UpdateConfig


class TaskState(Enum):
    NEW = "new"
    PENDING = "pending"
    ASSIGNED = "assigned"
    ACCEPTED = "accepted"
    READY = "ready"
    PREPARING = "preparing"
    STARTING = "starting"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    SHUTDOWN = "shutdown"
    REJECTED = "rejected"
    ORPHANED = "orphaned"
    REMOVE = "remove"


@dataclass
class Version:
    Index: int


@dataclass
class Status:
    Timestamp: str
    State: TaskState
    Message: str


@dataclass
class Task:
    ID: str
    Version: Version
    CreatedAt: str
    UpdatedAt: str
    Status: Status
    DesiredState: TaskState
    DeploymentID: str

    @staticmethod
    def from_dict(
        data: dict[str, str | int | dict[str, str | int]], deployment_id: str
    ) -> "Task":
        version = Version(**data["Version"])
        status_data = data["Status"]
        status = Status(
            Timestamp=status_data["Timestamp"],
            State=TaskState(status_data["State"]),
            Message=status_data["Message"],
        )
        return Task(
            ID=data["ID"],
            Version=version,
            CreatedAt=data["CreatedAt"],
            UpdatedAt=data["UpdatedAt"],
            Status=status,
            DeploymentID=deployment_id,
            DesiredState=TaskState(data["DesiredState"]),
        )


if __name__ == "__main__":
    client = docker.from_env()
    # endpoint_spec = EndpointSpec(ports={6382: 6379})
    # try:
    #     service = client.services.get("memcache_db")
    # except docker.errors.NotFound:
    service = client.services.create(
        image="memcached:latest",
        name="memcache_db",
        labels={"deployment": "first", "zane-managed": "true"},
        # mounts=['redis_data_volume:/data:rw'],
        # env=["REDIS_PASSWORD=strongPassword123"],
        # networks=['zane-out'],
        # endpoint_spec=endpoint_spec,
        # restart_policy=RestartPolicy(
        #     condition="on-failure",
        #     max_attempts=3,
        #     delay=5,
        # ),
        # update_config=UpdateConfig(
        #     parallelism=1,
        #     delay=5,
        #     monitor=10,
        #     order="start-first",
        #     failure_action="rollback"
        # ),
        # command="psql",
        # command="redis-server --requirepass ${REDIS_PASSWORD}"
        # labels={},
    )
    first_deploy_task_ID = service.tasks()[0]["ID"]
    print(json.dumps(service.tasks()))

    first_deploy_task = Task.from_dict(
        service.tasks(
            filters={"id": first_deploy_task_ID, "label": "deployment=first"}
        )[0],
        deployment_id="first",
    )
    # SHEDULE TO LISTEN TO THE DEPLOYMENT STATUS
    while first_deploy_task.Status.State != TaskState.RUNNING:
        time.sleep(0.1)
        print(first_deploy_task)

        first_deploy_task = Task.from_dict(
            service.tasks(
                filters={"id": first_deploy_task.ID, "label": "deployment=first"}
            )[0],
            deployment_id="first",
        )
    print(first_deploy_task)
    # result = service.scale(replicas=1)
    # for event in client.events(decode=True, filters={"service": "memcache_db"}):
    #     print(event)
    #     if event["status"] == "start" and event["Type"] == "container":
    #         break

    # print(json.dumps(service.tasks()))
    network = client.networks.get("net-prj_fUTgAByB8pH")
    service_spec = service.attrs["Spec"]
    current_networks = service_spec.get("TaskTemplate", {}).get("Networks", [])
    network_ids = set(net["Target"] for net in current_networks)
    network_ids.add(network.id)

    previous_task_length = len(service.tasks())
    service.update(networks=list(network_ids), labels={"deployment": "second"})

    # Wait until new task is added
    while len(service.tasks(filters={"label": "deployment=second"})) == 0:
        continue
    print(service.tasks())
    second_deploy_task_ID = service.tasks(filters={"label": "deployment=second"})[0][
        "ID"
    ]

    second_deploy_task = Task.from_dict(
        service.tasks(filters={"id": second_deploy_task_ID})[0],
        deployment_id="second",
    )
    print(second_deploy_task)
    # SHEDULE TO LISTEN TO THE DEPLOYMENT STATUS
    while second_deploy_task.Status.State != TaskState.RUNNING:
        time.sleep(0.1)
        print(second_deploy_task)

        second_deploy_task = Task.from_dict(
            service.tasks(
                filters={"id": second_deploy_task.ID, "label": "deployment=second"}
            )[0],
            deployment_id="second",
        )

    print(second_deploy_task)

    # print(json.dumps(service.tasks()))
    # for event in client.events(decode=True, filters={"service": "memcache_db"}):
    #     print(dict(event=event))
    #     if (
    #         event["Type"] == "service"
    #         and event.get("Action") == "update"
    #         and event.get("Actor", {}).get("Attributes", {}).get("updatestate.new")
    #         == "completed"
    #     ):
    #         break
    # print(json.dumps(service.tasks()))
    # service.update(networks=list())
    # while len(service.tasks()) == 2:
    #     time.sleep(0.5)
    # print(json.dumps(service.tasks()))
    # for event in client.events(decode=True, filters={"service": "memcache_db"}):
    #     print(dict(event=event))
    #     if (
    #         event["Type"] == "service"
    #         and event.get("Action") == "update"
    #         and event.get("Actor", {}).get("Attributes", {}).get("updatestate.new")
    #         == "completed"
    #     ):
    #         break
    # print(json.dumps(service.tasks()))
    # service.remove()
    pass
