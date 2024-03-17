import docker.errors
from docker.types import EndpointSpec, RestartPolicy, UpdateConfig

if __name__ == '__main__':
    client = docker.from_env()
    endpoint_spec = EndpointSpec(ports={6382: 6379})
    try:
        service = client.services.get("memcache_db")
    except docker.errors.NotFound:
        service = client.services.create(
            image='memcached:latest',
            name="memcache_db",
            # mounts=['redis_data_volume:/data:rw'],
            # env=["REDIS_PASSWORD=strongPassword123"],
            networks=['zane-out'],
            # endpoint_spec=endpoint_spec,
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

    result = service.scale(replicas=1)
    for event in client.events(decode=True, filters={'service': 'memcache_db'}):
        print(event)
        if event['status'] == 'start' and event['Type'] == 'container':
            break

    # service.update()
    # # print(dict(result=result))
    # for key, val in service.attrs.items():
    #     print(f"{key}={val}")
    # for log in service.logs(follow=True):
    #     print(dict(log=log))
    # service.scale(replicas=1)
