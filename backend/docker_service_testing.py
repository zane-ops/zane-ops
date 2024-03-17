import docker

from docker.types import EndpointSpec, RestartPolicy, UpdateConfig

if __name__ == '__main__':
    client = docker.from_env()
    endpoint_spec = EndpointSpec(ports={
        6382: 6379
    })
    client.services.create(
        image='redis:latest',
        name="cache_db",
        mounts=['redis_data_volume:/data:rw'],
        env=[
            "REDIS_PASSWORD=strongPassword123"
        ],
        networks=['zane-out'],
        endpoint_spec=endpoint_spec,
        restart_policy=RestartPolicy(
            condition="on-failure",
            max_attempts=3,
            delay=5,
        ),
        update_config=UpdateConfig(
            parallelism=1,
            delay=5,
            monitor=10,
            order="start-first",
            failure_action="rollback"
        ),
        # command="psql",
        # command="redis-server --requirepass ${REDIS_PASSWORD}"
        # labels={},
    )
    # client = docker.APIClient()
    #
    # volume = Mount(target="/data", source="redis_data_volume")
    # container_spec = ContainerSpec(
    #     image='redis:latest',
    #     mounts=[volume]
    #     # env={
    #     #     "REDIS_PASSWORD": "strongPassword123"
    #     # },
    #     # command="redis-server --requirepass ${REDIS_PASSWORD}"
    # )
    #
    # task_tmpl = TaskTemplate(container_spec)
    # endpoint_spec = EndpointSpec(ports={
    #     6382: 6379
    # })
    # service_id = client.create_service(
    #     task_tmpl,
    #     name='cache_db',
    #     endpoint_spec=endpoint_spec,
    #     networks=['zane-out'],
    # )

    # client.remove_service(service_id)
