# Multi-server — Implementation Plan

Status: **in design**. Branch `feat/multi-server`. Tracking issue: [#446](https://github.com/zane-ops/zane-ops/issues/446).

**What we want:** run ZaneOps across more than one machine — extra machines ("nodes") that run user services, extra machines that build images — while keeping the single-machine install working exactly as it does today.

**Hard requirement (from the issue thread):** 1 node, 2 nodes, 3 nodes must all work. No 3-node minimum, no forced shared storage. Replicated storage (data copied across multiple machines) is an *addon*, never a requirement.

---

## 1. What already exists

Some of the hardest prerequisites are already in the tree. Worth knowing before planning work that duplicates them.

| Piece | Where | Status for multi-node |
| --- | --- | --- |
| Build registry (local disk or S3) | [container_registry/models.py:60](../container_registry/models.py#L60) | ✅ **done** — built images are already pushed to a registry reachable over the `zane` overlay network, so any node can pull them. This was the biggest blocker and it is solved. |
| Per-worker task queue via env | [settings.py:456](../backend/settings.py#L456), [worker.py:67](../temporal/worker.py#L67) | ✅ the plumbing for per-node queues (a way to tell Temporal "run this job on that specific machine") is there; only the routing logic is missing |
| `swarm` app + `ServerNode` model | [swarm/models.py](../swarm/models.py) | 🚧 scaffolded, needs rework (see §3) |
| SSH keys + SSH-into-server terminal | [webshell/models.py:8](../webshell/models.py#L8), [server_terminal.py](../webshell/consumers/server_terminal.py) | ✅ reusable for setting up new nodes and running remote `docker exec` commands |
| `zane.role: proxy` label | [docker-stack.prod.yaml:53](../../docker/docker-stack.prod.yaml) | ✅ already labelled |
| Buildx builders (the thing that actually builds Docker images) | [git_activities.py:606](../temporal/activities/git_activities.py#L606) | ✅ they are **local `docker buildx` containers**, not Swarm services — see §4, this matters for who is allowed to build |
| Swarm service metrics | [helpers.py:754](../temporal/helpers.py#L754) | ⚠️ only checks the *local* machine, so it only sees containers running on the manager |

Everything in `docker-stack.prod.yaml` is currently pinned to `node.role==manager` (i.e. it only ever runs on the manager machine). That stays true for the control-plane pieces (API, DB, Temporal, etc).

---

## 2. The three decisions that shape everything else

### 2.1 Do NOT expose the manager's Docker socket to other nodes

A "Docker socket" is basically the API that lets you control Docker on a machine — if you have access to it, you can do almost anything on that machine. The original notes proposed connecting each remote build machine to the manager's Docker socket over a secure connection (TLS). I'd argue against it:

- it hands out full, root-level control of the whole cluster to every build machine
- it needs certificates, certificate rotation, and firewall rules — all things we'd have to build and maintain ourselves
- if one build machine gets compromised, the whole cluster is compromised

**Instead: split the work by what it actually needs.** Temporal lets you assign each individual job ("activity") to a specific queue, which is exactly the tool for this.

| Kind of job | Needs | Runs on queue |
| --- | --- | --- |
| Swarm changes — creating/updating/removing services, networks, configs, volumes | access to the manager's Docker API | `main-task-queue` (the manager's own worker, using its own local Docker) |
| Database / proxy / registry / Caddy config changes | nothing machine-specific | `main-task-queue` |
| Cloning code, detecting the build method, running `docker buildx build`, pushing the image | a local Docker socket + local disk on *that* machine | `build-<node>` (that node's own worker) |
| Reading local info — container metrics, `docker exec`, disk usage | a local Docker socket | `node-<node>` |

No machine ever needs remote access to another machine's Docker. Each worker only ever talks to its *own* local Docker socket.

**Task:** go through `git_activities.py` and double check that nothing in the build path secretly calls the Swarm API (which would need manager access). The buildx builders should already be fine since they're just local containers, but `main_activities.py`'s build helpers need checking too.

### 2.2 One "node worker" per node, not a whole separate program

The original notes proposed running a separate small monitoring program (like Portainer's "agent") on every node just to check health/metrics. That means building, shipping, upgrading, and securing a second piece of software — extra work for little benefit.

**Instead: run the existing ZaneOps app image as a service on every node**, each running its own Temporal worker listening on a queue named `node-<hostname>`. It already knows how to talk to the database and Temporal, it already has the Docker socket, and `make upgrade` already updates it. So "is this node allowed to build?" just becomes a label on the node, not a different program to install.

For checking whether a node is alive, we don't even need a special worker — `docker node ls` (a normal Swarm command) already tells the manager a node's `Status`, `Availability`, and `ManagerStatus`. We can just poll that on a schedule.

### 2.3 Worker nodes CAN build images

The GitHub issue originally said "worker nodes will not be able to run builds." But since building only needs a local Docker socket + local disk (not manager-level cluster control, per §2.1), that restriction isn't actually necessary — a plain worker node can build images just fine.

**Recommendation: keep two separate concepts apart.**
- `node.role` (manager/worker) — Swarm's own concept, about who has voting/cluster-control power
- `zane.build=true` — a label meaning "ZaneOps is allowed to schedule builds here"
- `zane.apps=true` — a label meaning "ZaneOps is allowed to run user services here"

That way, a 2-machine setup can be "1 manager doing everything + 1 worker that only does builds" — probably the most common real-world setup — without forcing anyone to add a second manager.

Still, we should document the general guidance around Swarm quorum (why you'd want an odd number of managers, and why 3 managers is the real "high availability" setup).

---

## 3. Data model

Rework [swarm/models.py](../swarm/models.py). The current draft has some leftover copy-paste issues (`ID_PREFIX = "tok_"` copied from the tokens feature, missing the shared `TimestampedModel` base, and no way to describe what a node is capable of).

```python
class ServerNode(TimestampedModel):
    ID_PREFIX = "node_"

    class Role(models.TextChoices):
        MANAGER = "MANAGER", _("Manager")
        WORKER  = "WORKER",  _("Worker")

    class Status(models.TextChoices):
        PROVISIONING = "PROVISIONING", _("Provisioning")
        READY        = "READY",        _("Ready")
        DOWN         = "DOWN",         _("Down")
        DRAINED      = "DRAINED",      _("Drained")
        FAILED       = "FAILED",       _("Failed")

    hostname       = models.CharField(unique=True)   # == swarm node Description.Hostname
    swarm_node_id  = models.CharField(unique=True)
    role           = models.CharField(choices=Role.choices)
    private_ip     = models.GenericIPAddressField()  # overlay / VPC address
    public_ip      = models.GenericIPAddressField(null=True)
    docker_version = models.CharField()
    status         = ...
    is_build_node  = models.BooleanField(default=False)
    is_app_node    = models.BooleanField(default=True)
    is_self        = models.BooleanField(default=False)   # the original manager, from the initial install
    ssh_key        = models.ForeignKey(SSHKey, on_delete=models.SET_NULL, null=True)
    ssh_user       = models.CharField(default="root")
    ssh_port       = models.PositiveIntegerField(default=22)
    cpus           = models.PositiveIntegerField(null=True)
    memory_bytes   = models.BigIntegerField(null=True)
    last_seen_at   = models.DateTimeField(null=True)

    @property
    def build_task_queue(self) -> str: return f"build-{self.hostname}"
    @property
    def node_task_queue(self)  -> str: return f"node-{self.hostname}"
```

**Migration for existing installs:** a data migration will automatically create one `ServerNode` row with `is_self=True`, reading the hostname/id straight from `docker.info()`. So every existing install instantly becomes a valid "1-node cluster" with no action needed from the user.

### Placement targeting (i.e. "which machine should this run on?")

Three levels, checked from most specific to least specific:

```
Service.node_placement  →  Environment.default_node_placement  →  Project.default_node_placement  →  ANY
```

Each of Service/Environment/Project stores a small choice field plus an optional link to a specific node:

| `placement_strategy` | Meaning |
| --- | --- |
| `ANY` | no constraint, Swarm decides |
| `ANY_APP_NODE` | any node labeled `zane.apps==true` |
| `SPECIFIC` | must run on `node.hostname==<placement_node.hostname>` |
| `PINNED_BY_VOLUME` | not chosen by the user — see §6, happens automatically when a service has saved data on a specific machine |

All of this gets resolved into an actual Swarm placement constraint in one place: [main_activities.py:1400](../temporal/activities/main_activities.py#L1400).

---

## 4. Build routing (Temporal)

Two modes, both needed.

**Explicit (the main case).** The deployment already knows which machine it should build on (from the placement rules above, or a manual override). The workflow just sends every build-related job to `task_queue=node.build_task_queue`. Simple and predictable — and it's exactly what "deploy this project on that specific server" needs anyway.

**Auto (fallback), used when placement is `ANY`.** We can use a known Temporal pattern called [worker_specific_task_queues](https://github.com/temporalio/samples-python/tree/main/worker_specific_task_queues): every build-capable worker also listens on one shared queue called `build-router`. A tiny first job goes out on that shared queue, and whichever worker happens to pick it up replies with its own personal queue name. The workflow then sends every following job in that same build to that specific worker's queue. So whichever machine is free grabs the job, and the rest of that build stays on that same machine.

Either way, the important rule stays the same: **every step of one build/deployment that touches the filesystem runs on the same machine.** That matters because the temporary folder used during a build ([`tmp_dir`, git_activities.py:370](../temporal/activities/git_activities.py#L370)) only exists on whichever machine created it — if a later step ran on a different machine, that folder wouldn't be there. This way we avoid needing shared storage (like S3) just for temp files, or re-cloning the repo at every step.

**On failure:** if a build fails, we do **not** try to retry it on a different machine — it just fails, and the user retries manually. This matches how it works today, keeps the change smaller, and was explicitly agreed on in the GitHub issue.

**Worker deployment:** the build worker will be a global Swarm service (meaning: one copy runs automatically on every eligible machine) restricted to nodes labeled `zane.build==true`. Its queue name needs to be based on the machine's own hostname — Swarm can fill in `{{.Node.Hostname}}` in an environment variable for us, which should work for this. Worth testing early; if it doesn't work, the fallback is to have `run_worker.sh` figure out the hostname itself at startup with `$(hostname)`.

---

## 5. Fluentd (log collection) — one setup, running identically everywhere

**Today:** there's one Fluentd (log collector) running on the manager, and every container is told to send its logs to a specific file path on disk (a "unix socket") at `${ZANE_APP_DIRECTORY}/.fluentd/fluentd.sock` ([main_activities.py:1444](../temporal/activities/main_activities.py#L1444)). If a container ran on a different machine, it would be pointing at a socket file that doesn't exist there — logging would break.

**Fix:** make `zane-fluentd` a **global service** (one copy automatically on every machine) and make sure every machine has that same file path set up. Since each machine evaluates that address locally, the *exact same* config keeps working with **zero code changes** — it just now works correctly everywhere because there really is a matching Fluentd on every machine.

This is why "ZaneOps must be installed at the exact same folder path on every machine" is a real, enforced requirement — not just a nice-to-have — and the setup process for adding a new node needs to guarantee it.

This also means we don't need the more complicated idea (from the original notes) of routing logs through Caddy to reach Fluentd — drop that. Each machine's Fluentd still sends logs the same way it does today, over the internal network to the central API, so there's still just one place logs get collected, and Loki (log storage/search) doesn't need to change at all.

---

## 6. Proxy (Caddy) — the part most likely to be underestimated

Making Caddy (the reverse proxy that routes web traffic to services) run on every machine is the easy part. Two things behind that are not.

**(a) Certificates.** Each Caddy instance needs to see the TLS certificates the others have already gotten — otherwise, each one will try to request its own certificate for the same domain and we'll hit Let's Encrypt's rate limits. Fix: use a plugin called [caddy-storage-redis](https://github.com/pberkel/caddy-storage-redis), pointed at the **Redis-compatible cache we already run** (`zane.valkey`) over the internal network.

I'd push back on the original notes' idea of "one Redis per server, clustered together" — for now, having a single shared cache (matching the manager) is fine, because the database, Temporal, and the API already only exist on the manager anyway — if the manager goes down, cert renewal is the least of our problems. We can add real Redis replication later, as part of a dedicated "high availability" phase. This does require rebuilding `docker/proxy/Dockerfile` to include the plugin.

**(b) Keeping every Caddy instance's config in sync — this is the actual hard part.** Right now, the API pushes routing changes to a single Caddy admin address, `http://zane.proxy:2019` ([settings.py:426](../backend/settings.py#L426)), using a "only apply if nothing else changed since I last read it" safety check (etag-based concurrency, see [proxy.py:16](../temporal/proxy.py#L16)). Once there are multiple Caddy instances behind one shared address, each update would only land on *one* of them at random, and the rest would silently fall out of sync.

Two ways to solve this:
1. **Send every change to every instance.** Switch `zane-proxy` to a mode (`endpoint_mode: dnsrr`) that lets us look up the IP of every single instance, then apply each config change to all of them individually. We already have most of the code needed to find those IPs: [`get_swarm_service_aliases_ips_on_network`](../temporal/helpers.py#L414). Downside: more requests per change, and we need to handle partial failures (what if it succeeds on 2 out of 3 machines?) and repeat that "safety check" retry logic per machine.
2. **One "leader" instance, others just copy it.** Keep a single Caddy on the manager as the source of truth, and have the rest load config from it. Caddy doesn't have a built-in way to do this, so we'd have to write our own syncing logic from scratch.

**Recommendation: option 1**, plus a periodic background job that checks each instance's actual config against what it *should* be, and fixes any mismatch. That also handles the case where a brand new machine joins after a config change already happened.

We should budget real time for this — it's the piece most likely to take longer than expected.

---

## 7. Volumes and storage

**For v1: stickiness, not real replication.** Meaning: if a service saves data to disk (a `Volume`, see [main.py:1662](../zane_api/models/main.py#L1662)), it will always be forced to run on the *same* machine it first ran on — not copied across machines.

- add a new field, `Volume.node`, linking to the `ServerNode` it landed on when it first deployed
- during placement resolution, a service with a volume tied to a node is automatically treated as `PINNED_BY_VOLUME`, which overrides any `ANY` setting
- show this clearly in the UI: "this service is pinned to node X because it has volumes"
- if someone wants to move that data to a different machine later, that has to be an explicit, manual action (stop the service, copy files over SSH, point it at the new machine, redeploy) — not something automatic

Note that `SharedVolume` ([main.py:1702](../zane_api/models/main.py#L1702)) is a *different* feature — it lets one service read another service's volume. With multiple machines, this means: if service A shares its volume with service B, then B must also be pinned to the same machine as A. We need to handle that when resolving placement.

**Later (not in v1): real replicated storage as an optional addon.** People discussing the GitHub issue converged on **Linstor/DRBD** rather than **Ceph** for this, for a good reason: Linstor works fine on a single machine and can expand to more, while Ceph needs at least 3 machines from day one — which breaks our "must work with 1 node" requirement.

Some commenters suggested we should prepare the folder structure for this on *every* install now (even single-node ones) to avoid a painful migration later. I'd hold off on that for v1 — it would mean installing extra kernel-level software (`drbd-dkms`) on every existing single-node install, for a feature most people won't ever use. Instead: just reserve the naming convention now (`/var/lib/zaneops/volumes/<volume_id>`), and start putting new volumes there. Turning on "replicated storage" later then only touches the storage layer underneath an already-stable path — same end result, without forcing extra software onto people who don't want it.

**Not covered by this plan, just documented:** moving app data to S3, or database replication setups. Those are considered the user's/template's own concern, per the discussion in the issue.

---

## 8. Shells and metrics on remote machines

Both of these currently assume everything is running locally, on the same machine as the API.

| Feature | Today | With multiple machines |
| --- | --- | --- |
| Opening a shell into a deployed container | `docker.from_env()` + `exec`, run locally ([container_terminal_consumer.py:29](../webshell/consumers/container_terminal_consumer.py#L29)) | look up which machine the container is actually running on (via the Swarm API), then SSH into that machine and run `docker exec` there — reusing the pattern already built in [server_terminal.py](../webshell/consumers/server_terminal.py) |
| Opening a shell into the server itself | SSH using a stored `SSHKey` | same as today, just let the user pick which machine in the UI |
| Container metrics (CPU/memory usage etc.) | read from the local socket ([helpers.py:826](../temporal/helpers.py#L826)) | run the same metrics-collecting job on each machine's own `node-<hostname>` queue, then combine the results |
| Picking which replica to connect to | doesn't exist yet | new UI: list all running copies of a service along with which machine each is on, let the user pick one |

Using SSH for remote shell access is a deliberate choice — it reuses infrastructure we already have, and doesn't require opening any new network port beyond the standard SSH port (22). The tradeoff is that it depends on SSH keys staying valid and reachable.

---

## 9. Setting up a new machine from the UI

This becomes a Temporal workflow, using SSH login details the user provides once.

1. connect via SSH, check the OS/CPU architecture/CPU count/memory, and confirm the manager can actually reach this machine's internal IP
2. install Docker if it's missing, and verify the version
3. create the ZaneOps folder **at the exact same path used on the manager**, and set up its config files (`.env`, `fluent.conf`, the Fluentd socket folder)
4. run `docker swarm join`, using a join token fetched from the manager, joining either as a manager or a worker
5. apply the right labels to the node (`zane.build`, `zane.apps`)
6. force-update the global services so Swarm notices the new machine and schedules things onto it
7. wait until Fluentd, the node worker, and the proxy are all reporting healthy on that machine
8. mark the `ServerNode` as `READY`

Each of these steps is written so it can safely be retried on its own — so if something fails partway through, we can resume instead of starting over. Removing a machine is basically the reverse: first do `docker node update --availability drain` (tell Swarm to stop scheduling new things there and move existing ones off), wait for that to finish, then remove it.

**Firewall:** Swarm itself needs certain ports open between machines: `2377/tcp` (for managers), `7946/tcp+udp`, and `4789/udp`. I'd recommend **not** having ZaneOps automatically configure the firewall (`ufw`) for the user in v1 — one wrong rule could lock the user out of their own machine over SSH, with no way for us to fix it remotely. Instead: clearly document the required ports, add a check that tells the user exactly which ports aren't reachable before they try to join a machine, and maybe add an opt-in "configure the firewall for me" button later.

---

## 10. Rollout phases

Each phase ends with a fully working cluster, so this can ship gradually instead of all at once.

| # | Phase | What's included | What becomes possible |
| --- | --- | --- | --- |
| 0 | Model + backfill | Rework `ServerNode`, auto-migrate every existing install into a valid 1-node cluster, add a read-only "list of nodes" screen in the UI | no visible behavior change yet |
| 1 | Node lifecycle | SSH-based setup workflow, joining/leaving/draining a machine, labels, port-reachability check, checking if a node is alive | you can add machines to the cluster; nothing runs on them yet |
| 2 | Multi-node data plane | Fluentd everywhere, Caddy everywhere + shared cert storage + **keeping every Caddy instance's config in sync** (§6), confirm image pulling works from a second machine | user services can actually run on any machine |
| 3 | Placement | Let Projects/Environments/Services choose where they run, volume pinning, `SharedVolume` handling, UI for picking a machine | users can choose where things run |
| 4 | Distributed builds | Split build jobs from cluster-control jobs (§2.1), per-machine build queues, both routing modes, global build worker service | builds no longer have to happen on the manager |
| 5 | Per-node operations | Node worker as a global service, combining metrics from all machines, SSH-based container shell, "pick a replica" UI | full visibility across all machines |
| 6 | Docs | Write a scaling guide: quorum, 1/2/3-machine setups, firewall rules, what counts as "high availability" and what doesn't | |
| 7 | High availability (separate effort) | Redis replication, Linstor as an optional addon, multiple managers | |

Phase 2 is the riskiest one. We should start testing the Caddy config-syncing approach (§6) early — even before phase 1 is fully done — because if option 1 doesn't work out, it affects phases 2 through 5.

---

## 11. Open questions

1. Can we get Swarm's `{{.Node.Hostname}}` template to fill in a worker's queue name automatically, or do we need `run_worker.sh` to compute it itself at startup? (cheap to test, blocks §4)
2. Does any existing build-related job secretly call the Swarm API (which would need manager access)? If so, §2.1 needs a fourth category of job. (blocks §2.1)
3. Where should we record which machine a deployment was built on — a field directly on the `Deployment` model, or only inside the workflow's internal state? A dedicated field would make retries and the UI simpler — leaning toward that.
4. If the machine a service is pinned to goes down, should new deployments to it fail right away, or wait until it comes back? Leaning toward failing fast with a clear error message.
5. `MAX_CONCURRENT_DEPLOYS` ([settings.py:459](../backend/settings.py#L459)) currently limits the whole cluster at once. Should each build machine have its own limit instead?
