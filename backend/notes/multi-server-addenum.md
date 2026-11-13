## TODO:

- [x] Wire `deploy-scripts/install.sh`/`Makefile` to `compose.prod.yaml` instead of `docker-stack.prod.yaml` — deliberately not done yet. Existing installs are all on `docker-stack.prod.yaml` (single-node: `node.role==manager` placement, no global services); switching the installer's target file is a breaking change for them, so it should ship as a major version bump, not a silent swap.

### Build/Deploy routing

- [x] Refresh the login to the build registry on all servers ? 
      - what if the root ssh key doesn't exist anymore ? -> no need
- [x] How to handle terminals to containers/replicas on other nodes: 
    -> Start a small websocket server on each `node-` worker
    -> When the user connects to `/ws/{container}` -> relay the websocket connection to the worker wich will run the terminal via `docker exec` 
      -> need to handle disconnect there as well
      -> Need to handle security (via the same permission class/mechanism for `InternalZaneAppPermission`)
- [ ] Update deployment to return tasks with containers from the healthcheck
- [ ] No need for multiple build registries, one is enough
- [ ] Fail git builds when there is more than one server if there is no Build registry
- [ ] Update service healthchecks (http/cmd) to use the container's IP instead of the container's ID
      Or run the healthcheck in the correct temporal-node worker (on the correct server)
      Remember that for services that aren't pinned to one server, the healthcheck will need to run on 
      all servers... or smth
      => This needs to be answered properly in the multi replicas workflow:
            -> how to handle healthcheck (especially on deploy)
            -> we need to totally change the UI to adapt and show all replicas
            -> What should happen if some replicas succeed healthcheck and other don't ? should we prevent the udpate ? -> probably
      => A service deployed with `ANY_DEPLOY_SERVER` will migrate if a node is unhealthy, will need to somehow migrate the healthcheck, or run the healthcheck everywhere ?
- [ ] Delete volumes should delete the volumes in the correct nodes (or all nodes ?) since a service can migrate
      accross nodes, volumes may have been created/leftover
- [ ] How to Handle healthcheck for services with multiple replicas ?
- [ ] Fix `schedule-task-queue` task queue not existing anymore


### Swarm node workflows — safety

- [x] When joining, if the server already belongs to another swarm (e.g. the user's own), fail with a clear error - today we run `docker swarm leave --force` first, which destroys that other swarm
- [x] Stop printing the output of `docker swarm join-token` in `get_swarm_join_token` — it contains the secret join token, which ends up in the worker logs

### Swarm node workflows — robustness

- [x] Wrap both workflows in `try/finally` — if an activity crashes, the SSH keys stay on disk and the node stays stuck in `PROVISIONING` forever
- [x] Before provisioning, check the server's OS/CPU architecture, that the manager can reach its private IP, and that the swarm ports are open (`2377/tcp`, `7946/tcp+udp`, `4789/udp`) — see [§9 of the plan](multi-server-plan.md#sec-9)
- [x] Make activities raise `ApplicationError` instead of returning `False`/`None` — right now failures are never retried and the node shows `FAILED` without saying why (store the reason on the node for the UI)
- [x] Only allow one workflow per node at a time — workflow IDs include a timestamp, so a provision and a removal of the same node can run at the same time
- [x] Add heartbeats to long activities (docker install, waiting for services) 
- [x] Allow removing a node that is dead/unreachable — the removal workflow needs SSH on the node, so it gets stuck; add a "force" option that only runs `docker node rm --force` from the manager
- [x] Re-running a removal that already got past "leave swarm" gets stuck — `docker swarm leave` errors with "not part of a swarm", so we never reach `docker node rm`; treat that error as success
- [x] Re-provisioning a node with a different role (e.g. worker → manager) makes it rejoin with a new swarm ID, and the old entry stays in `docker node ls` as `Down` — remove the old one
- [x] `update_node_labels` overwrites all node labels, so labels a user added by hand get deleted — only add/update the ZaneOps labels

- [x] Add an `UpdateSwarmNodeWorkflow` to change a node's role (`docker node promote/demote`) and availability (`docker node update --availability active|pause|drain`), only allowed on `ACTIVE`/paused/drained nodes — so the provision workflow only handles the first setup, and changing a role doesn't require removing and re-adding the node
- [x] Add a scheduled check of node health (`docker node ls`) — nodes left in `PROVISIONING` are never re-checked, and we don't notice when a node goes `DOWN`
- [x] Also wait for `zane-temporal-node-worker` and `zane-temporal-build-worker` in `wait_for_global_services_to_be_propagated` — today it only waits for the proxy and Vector (only expect the build worker on nodes with the `BUILD_SERVER` role)

## Notes

- Adding a new server to ZaneOps:
  1. stop all services (`make stop`)
  2. leave swarm (`docker swarm leave -f`) if IP addr is local IP (`127.0.0.1`)
  3. recreate swarm with private VPC IP: `docker swarm init --advertise-addr <PRIVATE_IP>`
  4. Recreate `zane` network (`make setup`)
  5. Start ZaneOps (`make deploy`)
  6. Run job to fix swarm state: `python manage.py fix_swarm_networking`


### Later ->>

- Compose Stacks services should have a node constraint with: zane.app-server=true so that they are only deployed to app servers (by default)
- Check why compose stacks don't seem to run healthcheck correctly
- The API endpoint that removes a node must first check if any service has a volume on that node, and block (or warn) — once the node is drained, these services can't start anywhere else (they stay `Pending`), and their data is lost when the node is removed. The management commands skip this check, they're only for testing.
- The node removal endpoint/UI must warn if removing a manager would leave too few managers to keep the cluster working (quorum, see [§14 of the plan](multi-server-plan.md#sec-14)).
- When removing a manager node: demote it to worker first, refuse to remove the main server (`is_self`) or the last manager
- In the docs, we can only add servers with the same architecture as the main server, we need to explain that it's so that images & services work between nodes, because some images are single arch
- We need to add `node_id` to compose service tasks, in `temporal/helpers/get_compose_stack_swarm_service_status` and in `compose/views/serializers/ComposeStackServiceTask`