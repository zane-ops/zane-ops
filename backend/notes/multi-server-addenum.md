## TODO:

- ~~Add port to SSHKey handling.~~
- ~~Adapt docker-stack.prod.yaml/compose.prod.yaml stacks~~
- Wire `deploy-scripts/install.sh`/`Makefile` to `compose.prod.yaml` instead of `docker-stack.prod.yaml` — deliberately not done yet. Existing installs are all on `docker-stack.prod.yaml` (single-node: `node.role==manager` placement, no global services); switching the installer's target file is a breaking change for them, so it should ship as a major version bump, not a silent swap.

## Notes

- Adding a new server to ZaneOps:
  1. stop all services (`make stop`)
  2. leave swarm (`docker swarm leave -f`) if IP addr is local IP (`127.0.0.1`)
  3. recreate swarm with private VPC IP: `docker swarm init --advertise-addr <PRIVATE_IP>`
  4. Recreate `zane` network (`make setup`)
  5. Start ZaneOps (`make deploy`)
  6. Run job to fix swarm state: `python manage.py fix_swarm_networking`

- [x] Add a Job for fixing swarm state error when changing `advertise-addr` (and recreating swarm state)
  - Implemented as a Django management command instead of a Temporal job — `fix_swarm_networking` ([swarm/management/commands/fix_swarm_networking.py](../swarm/management/commands/fix_swarm_networking.py))
  - `docker swarm leave -f` + fresh `docker swarm init` wipes every network and service Swarm knows about (not just the ones tied to the old advertise-addr), so the fix isn't a light touch-up: it recreates every environment's overlay network, then redeploys every `Service` and `ComposeStack` from scratch using ZaneOps' own DB records (same `prepare_new_docker/git_deployment` + `TemporalClient.start_workflow` path as a normal manual redeploy, just looped over everything on the instance)
  - Prompts for confirmation before running (`--yes` to skip) since it redeploys the entire instance

## Files needed on every non-main node

Global services in [compose.prod.yaml](../../docker/compose.prod.yaml) bind-mount host paths, and Swarm does **not** create missing bind sources — the task stays in `Pending`/restart loop until they exist. So before (or right after) a node joins, `ZANE_APP_DIRECTORY` must exist **at the exact same path as on the main node** (default `/var/www/zaneops`) with:

| Path (relative to `ZANE_APP_DIRECTORY`) | Source in repo | Used by                                                     |
| --------------------------------------- | -------------- | ----------------------------------------------------------- |
| `.fluentd/` (empty dir, `chmod 777`)    | —              | `zane-fluentd` socket, every container's fluentd log driver |

Nothing else: `zane-temporal-node-worker` / `zane-temporal-build-worker` only mount `/var/run/docker.sock` and named volumes (created per node automatically), and their env is baked into the service spec — no `.env` needed on other nodes. Same for `pgbouncer/`, `temporalio/`, `loki-config.yaml`: those are only mounted by services pinned to `zane.main-server`.
