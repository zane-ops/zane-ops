# External build registries

Exploration notes — not a decided plan. Items marked _(verify)_ are assumptions that need checking before building anything.

## Why only managed registries today

No written rationale was found (no notes, PR #533 has no description). Reading of the code:

- `BuildRegistry` ([models.py:59](../container_registry/models.py#L59)) is a **managed Swarm service**: `swarm_service_name`, `service_alias`, `health_status`, deploy/monitor/destroy workflows, `storage_backend`.
- Credentials are a static `registry_username` / `registry_password`.
- Image listing uses `/v2/_catalog` ([build_registries.py:122](../container_registry/views/build_registries.py#L122)), which most cloud registries don't support.
- HTTP logs and the on-demand TLS check assume ZaneOps proxies the registry through Caddy.

Hint that external was considered: `SharedRegistryCredentials.RegistryType` already has `AWS_ECR` / `GOOGLE_ARTIFACT` / `GITHUB` / `GITLAB` (pull only), and the `storage_backend` comment says "Only meaningful for managed registries".

## How push works today

Every build runs `docker login <registry_domain> -u … --password-stdin` in `login_to_global_build_registry` ([git_activities.py:106](../temporal/activities/git_activities.py#L106)), using the values from `get_default_build_registry`. So an external registry only needs a valid password **at build time** — resolve/refresh it in `get_default_build_registry`, the login stays the same.

## Model sketch

- `registry_type`: `MANAGED | GENERIC | AWS_ECR | GOOGLE_ARTIFACT | GITHUB | GITLAB`
- `credentials` JSON field per type (same pattern as `s3_credentials`)
- **image path prefix** — `registry_domain` alone isn't enough, every provider below needs a namespace path
- skip deploy / monitor / destroy workflows, Caddy routing and TLS check when type ≠ `MANAGED`
- `list-images` dispatches per type instead of always calling `/v2/_catalog`

## Per provider

| | Credentials | Expires | Image prefix | Repo must exist before push | Listing |
| --- | --- | --- | --- | --- | --- |
| **Google Artifact Registry** | user `_json_key`, password = service account JSON | no | `<region>-docker.pkg.dev/<project>/<repo>/` | yes | Artifact Registry API _(verify `_catalog` support)_ |
| **AWS ECR** | access key id + secret + region → `ecr.get_authorization_token()` (boto3, already installed) | **12h token** | `<acct>.dkr.ecr.<region>.amazonaws.com/` | yes — `ecr.create_repository` or document as prerequisite | `describe_repositories` (no `_catalog`) |
| **GitHub (ghcr.io)** | GitHub user + **classic** PAT with `write:packages` | no (unless set on the PAT) | `ghcr.io/<owner>/` | no, created on first push | REST `GET /orgs/{org}/packages?package_type=container` (no `_catalog` _(verify)_) |
| **GitLab** | deploy token or project/group access token with `write_registry` (+ `read_registry`) | deploy tokens: optional · access tokens: mandatory expiry (~1y max) _(verify)_ | `registry.gitlab.com/<group>/<project>/` (or self-hosted domain) | **project** must exist; images live under it | REST `GET /projects/:id/registry/repositories` |

### Google Artifact Registry
- Works almost with the current generic model (`_json_key` is static).
- Needs the path prefix.

### AWS ECR
- Store keys, not a password; fetch a fresh token before each build login (easy).
- **Pull side is the hard part** — see below.

### GitHub (ghcr.io)
- Fits the static-credentials model.
- Fine-grained PATs don't support Packages _(verify)_.
- Reusing the GitHub App connectors ([git_connectors/](../git_connectors/)) probably doesn't work: GHCR seems to only accept classic PATs / `GITHUB_TOKEN` _(verify)_, and installation tokens expire after 1h anyway (same refresh problem as ECR).
- Packages pushed with a PAT are private by default; private storage is billed past the free quota — worth a UI hint.

### GitLab
- Deploy tokens without expiry fit the static model best; recommend those in the UI.
- Can't push to an arbitrary namespace — images must sit under an existing project (path depth under the project is limited _(verify)_).
- Self-hosted GitLab: registry domain is separate from the GitLab domain and may be disabled on the instance.
- Reusing the GitLab connector's OAuth token would need the `write_registry` scope and those tokens expire (~2h) _(verify)_ → refresh problem again.
- Cleanup: project cleanup policies or the tags delete API.

## Pull side (multi-server concern)

- Swarm stores registry auth in the service spec at create/update time (`--with-registry-auth`).
- With an **expiring token** (ECR, GitHub App / GitLab OAuth tokens), a task rescheduled to another node after expiry likely fails to pull _(verify)_.
- Options:
  - scheduled job refreshing auth on affected services (e.g. every ~6h for ECR)
  - credential helpers on each node — unclear if Swarm workers use them, it's a CLI-side feature _(verify)_
- Static credentials (GAR JSON key, GitHub classic PAT, GitLab deploy token) don't have this problem.

## Open questions

- [ ] Test Swarm pull with an expired ECR token on a rescheduled task
- [ ] Check `_catalog` support on GAR / ghcr.io
- [ ] Check fine-grained PAT + GitHub App token support on ghcr.io
- [ ] Check GitLab access token max expiry and image path depth limits
- [ ] Decide whether image cleanup is ZaneOps' job or left to provider lifecycle policies
