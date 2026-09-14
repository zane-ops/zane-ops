## TODO:

Add port to SSHKey handling.

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