# Multi-server — Implementation Plan

Status: **in design**. Branch `feat/multi-server`. Tracking issue: [#446](https://github.com/zane-ops/zane-ops/issues/446).

**What we want:** run ZaneOps across more than one machine — extra nodes that run user services, extra nodes that run builds — while keeping the single-node install working exactly as it does today.

**Hard requirement (from the issue thread):** 1 node, 2 nodes, 3 nodes must all work. No 3-node minimum, no forced shared storage. Replicated storage is an *addon*, never a prerequisite.

---

## 1. What already exists

Some of the hardest prerequisites are already in the tree. Worth knowing before planning work that duplicates them.

| Piece | Where | Status for multi-node |
| --- | --- | --- |
| Build registry (local disk or S3) | [container_registry/models.py:60](../container_registry/models.py#L60) | ✅ **done** — built images are already pushed to a registry reachable over the `zane` overlay, so any node can pull them. This was the biggest blocker and it is solved. |
| Per-worker task queue via env | [settings.py:456](../backend/settings.py#L456), [worker.py:67](../temporal/worker.py#L67) | ✅ the plumbing for per-node queues is there; only the routing is missing |
| `swarm` app + `ServerNode` model | [swarm/models.py](../swarm/models.py) | 🚧 scaffolded, needs rework (see §3) |
| SSH keys + SSH-into-server terminal | [webshell/models.py:8](../webshell/models.py#L8), [server_terminal.py](../webshell/consumers/server_terminal.py) | ✅ reusable for node provisioning and remote `docker exec` |
| `zane.role: proxy` label | [docker-stack.prod.yaml:53](../../docker/docker-stack.prod.yaml) | ✅ already labelled |
| Buildx builders | [git_activities.py:606](../temporal/activities/git_activities.py#L606) | ✅ they are **local `docker buildx` containers**, not swarm services — see §4, this changes who can build |
| Swarm service metrics | [helpers.py:754](../temporal/helpers.py#L754) | ⚠️ runs against the *local* socket, so it only sees containers on the manager |

Everything in `docker-stack.prod.yaml` is pinned `node.role==manager` today. That stays true for the control plane.

---

## 2. The three decisions that shape everything else

### 2.1 Do NOT expose the manager's Docker socket to other nodes

The notes propose connecting each remote worker to the manager's Docker socket over TLS. I'd argue against it:

- it puts full root-equivalent cluster control on the wire, on every build node
- it needs a CA, cert rotation, and a firewall story, all of which we'd have to build and maintain
- it makes a compromised build node a compromised cluster

**Instead: split the activities by what they need.** Temporal lets you pick a task queue *per activity*, which is exactly the tool for this.

| Activity kind | Needs | Runs on queue |
| --- | --- | --- |
| Swarm mutations — `services.create/update/remove`, networks, configs, volume creation | manager API | `main-task-queue` (manager worker, local socket) |
| DB / proxy / registry / Caddy config | nothing node-local | `main-task-queue` |
| Clone, buildpack detect, `docker buildx build`, push | a local Docker socket + local disk | `build-<node>` (that node's worker, local socket) |
| Node-local reads — container metrics, `docker exec`, disk usage | a local Docker socket | `node-<node>` |

No remote sockets anywhere. Each worker only ever talks to `/var/run/docker.sock` on its own host.

**Task:** audit `git_activities.py` end-to-end and confirm no build-path activity touches a swarm API. The buildx builders are `docker-container` driver, so they should be clean — but `main_activities.py` build helpers need checking too.

### 2.2 One "node worker" per node, not a separate agent

The notes propose a Portainer-style agent container for health and metrics. We don't need a second thing to build, ship, upgrade and secure.

**Run the existing app image as a global swarm service on every node**, one Temporal worker each, listening on `node-<hostname>`. It already has the Docker socket mounted, it already knows how to talk to the DB and Temporal over the overlay, and `make upgrade` already updates it. "Is this node a build server?" becomes a swarm node label, not a different binary.

For node *liveness* we don't need an agent at all — `docker node ls` from the manager already reports `Status`, `Availability` and `ManagerStatus`. Poll it on the schedule queue.

### 2.3 Worker nodes CAN build

The issue says "worker nodes will not be able to run builds". Given 2.1, that restriction doesn't hold: building needs a local socket and local disk, not manager membership. Buildx builders are plain containers.

**Recommendation:** decouple the two axes.
- `node.role` (manager/worker) — swarm's own concept, about quorum
- `zane.build=true` node label — whether ZaneOps schedules builds here
- `zane.apps=true` node label — whether ZaneOps schedules user services here

A 2-node setup then works as "1 manager running everything + 1 worker doing builds only", which is the most common thing people will actually want, and doesn't force a second manager.

Still document the quorum guidance (odd number of managers, 3 for real HA).

---

## 3. Data model

Rework [swarm/models.py](../swarm/models.py). Current draft has `ID_PREFIX = "tok_"` (copy-paste from tokens), no `TimestampedModel`, and no way to express capabilities.

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
    is_self        = models.BooleanField(default=False)   # the bootstrap manager
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

**Migration for existing installs:** a data migration creates one `ServerNode` with `is_self=True`, reading hostname/id from `docker.info()`. Every existing install becomes a valid 1-node cluster with no user action.

### Placement targeting

Three levels, most specific wins:

```
Service.node_placement  →  Environment.default_node_placement  →  Project.default_node_placement  →  ANY
```

Stored as a small embedded choice + optional FK, on each of the three models:

| `placement_strategy` | Meaning |
| --- | --- |
| `ANY` | no constraint, swarm decides |
| `ANY_APP_NODE` | `node.labels.zane.apps==true` |
| `SPECIFIC` | `node.hostname==<placement_node.hostname>` |
| `PINNED_BY_VOLUME` | implicit — see §6 |

Resolved into `Placement(constraints=[...])` at the one place that builds the service spec, [main_activities.py:1400](../temporal/activities/main_activities.py#L1400).

---

## 4. Build routing (Temporal)

Two modes, both needed.

**Explicit (primary).** The deployment already knows its target node, from the placement chain above or a `build_node` override. The workflow just uses `task_queue=node.build_task_queue` for every build activity. Deterministic, and it's what the "deploy this project on that server" feature needs anyway.

**Auto (fallback), for `ANY`.** Use Temporal's [worker_specific_task_queues](https://github.com/temporalio/samples-python/tree/main/worker_specific_task_queues) trick: all build workers also listen on a shared `build-router` queue; a tiny `get_my_build_queue()` activity on that queue returns the answering worker's own unique queue name; the workflow pins every subsequent build activity to it. Whoever is free picks it up, and the rest of the build stays on that machine.

Either way the result is the same invariant: **all filesystem-dependent steps of one deployment run on one node**, so `tmp_dir` from [git_activities.py:370](../temporal/activities/git_activities.py#L370) stays valid across steps. No S3 tmp dir, no re-clone per step.

**On failure:** no cross-node retry. The deployment fails, the user retries. Matches today's behaviour and keeps the change small (explicitly agreed in the issue).

**Worker deployment:** the build worker becomes a global swarm service constrained to `node.labels.zane.build==true`, with `TEMPORALIO_WORKER_TASK_QUEUE` set per-task. Swarm can't template an env var from the hostname directly in a useful way for our queue naming — set it from `{{.Node.Hostname}}`, which swarm *does* support in `env`. Worth verifying early; the fallback is `run_worker.sh` computing the queue from `$(hostname)` at startup.

---

## 5. Fluentd — global service, same path everywhere

Today: one replica on the manager, unix socket at `${ZANE_APP_DIRECTORY}/.fluentd/fluentd.sock`, and every container is created with `fluentd-address: unix://<that path>` ([main_activities.py:1444](../temporal/activities/main_activities.py#L1444)). A container on node B would point at a socket that doesn't exist there.

**Fix: make `zane-fluentd` `mode: global`** and mount the same host path on every node. The log driver options are evaluated by the daemon on whichever node runs the task, so the *existing* address string keeps working unchanged, on every node, with zero code change.

This is why "ZaneOps must be installed at the same path on every node" is a real constraint, not a convenience — the provisioning flow must enforce it.

This makes the Caddy-reverse-proxy-to-fluentd idea from the notes unnecessary. Drop it. Each node's fluentd still ships over the overlay to `zane.api.zaneops.internal`, so there's still exactly one ingestion endpoint and Loki is unchanged.

---

## 6. Proxy — the under-estimated part

Making Caddy `mode: global` is easy. Two things behind it are not.

**(a) Certificate storage.** Each Caddy instance needs to see the others' certs, or they'll each solicit their own and hit ACME rate limits. Use [caddy-storage-redis](https://github.com/pberkel/caddy-storage-redis) pointed at the **existing single `zane.valkey`** over the overlay.

I'd push back on the notes' "redis cluster, one per server". A cert store that is only as available as the manager is fine for v1, because the DB, Temporal and the API are all on the manager too — if it's gone, you have bigger problems than cert renewal. Add Valkey replication in the HA phase, not now. Requires rebuilding `docker/proxy/Dockerfile` with the plugin.

**(b) Config fan-out — this is the real work.** The API pushes routes to a single admin endpoint, `http://zane.proxy:2019` ([settings.py:426](../backend/settings.py#L426)), and `ZaneProxyClient` uses etag-based optimistic concurrency ([proxy.py:16](../temporal/proxy.py#L16)). With a global service behind a VIP, each `PATCH` lands on one arbitrary instance and the others silently drift.

Options:
1. **Fan out.** Switch `zane-proxy` to `endpoint_mode: dnsrr`, resolve `tasks.zane-proxy` to every task IP, and apply each mutation to all of them. [`get_swarm_service_aliases_ips_on_network`](../temporal/helpers.py#L414) already does most of the resolution. Downside: N× requests, partial-failure handling, and the etag retry loop has to be per-instance.
2. **Single writer + replicated read.** Keep one "config leader" Caddy on the manager, have the others load config from a shared source. Caddy has no first-class config replication, so this means a sync loop we write ourselves.

**Recommendation: option 1**, plus a reconciliation pass on the schedule queue that periodically diffs each instance's `/config/` against the intended state and repairs drift. That covers the case of a node joining after a config change.

Budget real time for this; it is the piece most likely to be underestimated.

---

## 7. Volumes and storage

**v1: stickiness, not replication.** Any service with a `Volume` ([main.py:1662](../zane_api/models/main.py#L1662)) gets an implicit `node.hostname==<node>` constraint, and we record which node the data landed on.

- add `Volume.node = FK(ServerNode, null=True)`, set on first deploy
- placement resolution treats a service with any node-bound volume as `PINNED_BY_VOLUME`, overriding `ANY`
- surface it in the UI: "this service is pinned to node X because it has volumes"
- moving it later = an explicit, user-initiated migration (stop, rsync over SSH, repoint, redeploy)

Note `SharedVolume` ([main.py:1702](../zane_api/models/main.py#L1702)) is a *different* concept — one service reading another's volume. Multi-node makes that constraint transitive: a reader must be pinned to the same node as the writer. Handle that in placement resolution.

**Later: replicated storage as an addon.** Both commenters on the issue converge on **Linstor/DRBD over Ceph**, for one reason that matters to us a lot: Linstor works on a single node and expands to N, while Ceph needs 3 nodes from day one. That fits the "must work on 1 node" requirement.

The commenters make a fair point that pre-creating the mount path on *every* install (even single-node) avoids a painful migration later. I'd still not do it in v1 — it means shipping a kernel module (`drbd-dkms`) to every existing single-node install for a feature most of them will never use. Instead: reserve the path convention now (`/var/lib/zaneops/volumes/<volume_id>`), switch new volumes to bind mounts at that path, and make "enable replicated storage" a later migration that only touches the storage layer beneath an already-stable path. Same end state, no kernel module for people who don't want one.

**Out of scope, document only:** offloading app state to S3, DB replication topologies. Those are template/user concerns, per the issue thread.

---

## 8. Shells and metrics on remote nodes

Both currently assume everything is local.

| Feature | Today | Multi-node |
| --- | --- | --- |
| Deployment shell | `docker.from_env()` + `exec` ([container_terminal_consumer.py:29](../webshell/consumers/container_terminal_consumer.py#L29)) | find the task's node from the swarm API, then SSH to it and `docker exec` — reuse the pattern already in [server_terminal.py](../webshell/consumers/server_terminal.py) |
| Server shell | SSH with an `SSHKey` | same, but pick the node in the UI |
| Container metrics | local socket ([helpers.py:826](../temporal/helpers.py#L826)) | run the collector activity on each `node-<hostname>` queue, fan in |
| Replica picker | n/a | new UI: list tasks with their node, pick one to attach to |

SSH-for-exec is worth calling out as a deliberate choice: it reuses machinery we already have and needs no new inbound port beyond 22, at the cost of depending on SSH keys staying valid.

---

## 9. Provisioning a node from the UI

A Temporal workflow, driven by SSH creds the user supplies once.

1. probe: SSH in, read OS/arch/cpus/memory, check the private IP is reachable from the manager
2. install Docker if absent, verify version
3. create `${ZANE_APP_DIRECTORY}` **at the same path as the manager**, drop `.env`, `fluent.conf`, the fluentd socket dir
4. `docker swarm join` with a token fetched from the manager, as manager or worker
5. apply node labels (`zane.build`, `zane.apps`)
6. `docker service update --force` the global services so they schedule onto the new node
7. wait for fluentd + node worker + proxy to report healthy there
8. mark the `ServerNode` `READY`

Each step is an idempotent activity so a partial failure can be resumed. Removal is the reverse, with a `docker node update --availability drain` and a wait for tasks to reschedule first.

**Firewall:** swarm needs `2377/tcp` (managers), `7946/tcp+udp`, `4789/udp` between nodes. I'd **not** have ZaneOps configure `ufw` automatically in v1 — a wrong rule locks the user out of their own box, over SSH, with no recovery path from our UI. Document the rules, add a *preflight check* that tells the user exactly which ports are unreachable, and consider an opt-in "configure firewall for me" later.

---

## 10. Phases

Each phase ends with a working cluster, so this can ship incrementally.

| # | Phase | Contents | Ships |
| --- | --- | --- | --- |
| 0 | Model + backfill | `ServerNode` rework, data migration making every existing install a 1-node cluster, read-only nodes list in the UI | no behaviour change |
| 1 | Node lifecycle | SSH provisioning workflow, join/leave/drain, labels, preflight port check, node status polling | can add nodes; nothing schedules on them yet |
| 2 | Data-plane multi-node | fluentd global, proxy global + redis cert storage + **config fan-out**, verify registry pull from a second node | user services can run on any node |
| 3 | Placement | placement chain on Project/Env/Service, volume pinning, `SharedVolume` transitivity, UI selectors | users choose where things run |
| 4 | Distributed builds | activity split (§2.1), per-node build queues, explicit + auto routing, global build worker service | builds run off the manager |
| 5 | Node-local ops | node worker global service, remote metrics fan-in, SSH-based deployment shell, replica picker | full observability across nodes |
| 6 | Docs | scaling guide: quorum, 1/2/3-node topologies, firewall, what is and isn't HA | |
| 7 | HA (separate) | Valkey replication, Linstor addon, multi-manager control plane | |

Phase 2 is the risky one. Start the proxy config fan-out spike early — before phase 1 is finished — because if option 1 in §6 doesn't hold up, phases 2–5 all move.

---

## 11. Open questions

1. Can swarm's `{{.Node.Hostname}}` template be used in the worker's `env` to derive its task queue, or do we compute it in `run_worker.sh`? (cheap to test, blocks §4)
2. Does any build-path activity call a swarm API? If yes, §2.1 needs a fourth activity class. (blocks §2.1)
3. Where does the deployment *record* store its chosen build node — a field on `Deployment`, or only in workflow state? A field makes retries and the UI simpler; leaning field.
4. When a pinned node goes down, do we fail deployments to it fast, or queue them? Leaning fail fast with a clear error.
5. `MAX_CONCURRENT_DEPLOYS` ([settings.py:459](../backend/settings.py#L459)) is currently global. Should it become per-build-node?
