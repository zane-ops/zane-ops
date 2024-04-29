## How to healthcheck and blue-green ?

Should we ?

- reimplement what docker does ? -> YES
- add blue-green servers to caddy -> YES

### what we will use :

- On service creation :
    1. use docker swarm tasks values by default with a strong retry policy
        1. to check if a service is up, we need to check if a task is running first
    2. Manually run the healthcheck by ourselves regularly, and report the status to the user, if they defined one

- On service update :
    1. `...same as before`
    2. Create another service and inspect the previous network alias deployment for the service
        1. we will use the same service alias as the current production deploy for services so that it is available by
           other services ( `service-alias.zaneops.internal` )
        2. if the service was `blue`, we choose `green`, else we
           choose `blue` (`service-alias.zaneops.internal.<blue|green>`)
    3. Monitor the health of the newly created service with the healthcheck params of the service
       with a scheduled job,
        1. if the service fails to meet the health status requirements, we remove the service for the
           deployment
        2. if the service succeed to meet the requirements, we remove the previous service
    4. we mark the deployment as finished and release the lock for the deployment

- On caddy side :
    1. use the service network alias instead of the service name
    2. use a blue-green setup, but using the initial healthcheck value :
       ```shell
        service-domain.com {
          handle /path/* {
             reverse_proxy service-alias.zaneops.internal.blue service-alias.zaneops.internal.green {
                lb_policy first # always choose the first available service before the next
                fail_duration 30s # How long to hold that a proxy is down

                health_path /<healthcheck-path>
                health_status 2xx
                health_interval <healthcheck-interval>s
                health_timeout <healthcheck-timeout>s
             }
          }
        }
       ```
    3. If healthcheck has changed, we will modify the caddy proxy after we are sure that the new service is up.
    4. Caddy will always redirect to the first available upstream

### Other important things (in another PR)

- We need to make sure only one deployment task is running at a time, so if a deployment is running,
  we will wait for the previous deployment to finish, We can do that with locking :
    - https://stackoverflow.com/questions/9811933/celery-design-help-how-to-prevent-concurrently-executing-tasks
    - http://loose-bits.com/2010/10/distributed-task-locking-in-celery.html
    - https://docs.celeryq.dev/en/stable/tutorials/task-cookbook.html#ensuring-a-task-is-only-executed-one-at-a-time
- We need to attach a snapshot object of the config in each deployment to allow to reapply them if we redeploy
  one
    - will be included: healthcheck, urls, ports (config), tag, image and volumes, envs will stay the same.
    - We need a URL that computes the changeset between two deploys to warn the user about the changes when deploying