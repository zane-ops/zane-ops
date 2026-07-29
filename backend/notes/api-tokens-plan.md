# API Tokens — Implementation Plan

Status: **planned**, not started. To be built on its own branch.

**What we want:** let people call the ZaneOps API with a token in a header instead of a login cookie, so that CI pipelines and scripts can use it. Right now only a browser with a session cookie can talk to the API.

**Why now:** the three deploy webhook routes are currently open to anyone who knows the URL (`AllowAny`). See [§7](#7-deploy-webhooks--the-main-reason-were-doing-this). That is the one known hole in our permission system ([PERMISSIONS_CHANGELIST.md](./PERMISSIONS_CHANGELIST.md) §1).

---

## 1. How things work today

| Piece | Where | What it does |
| --- | --- | --- |
| Authentication | [settings.py:298](../backend/settings.py#L298) | `SessionAuthentication` only — cookie from a browser login |
| Default permissions | [settings.py:294](../backend/settings.py#L294) | `[HasWorkspace, IsWorkspaceViewer]` |
| Finding the workspace | [permissions.py:39](../zane_api/permissions.py#L39) | `HasWorkspace` reads `current_workspace_id` out of the **session**, then puts the workspace on `request.workspace` |
| Roles | [main.py:79](../zane_api/models/main.py#L79) | `WorkspaceRole` — numbers that sort (Viewer 10 < Member 30 < Admin 40 < Owner 50). `CONTRIBUTOR = 20` exists but is commented out |
| Role checks | [permissions.py](../zane_api/permissions.py) | `IsWorkspaceViewer/Member/Admin/Owner`, `has_min_role()` |
| Which projects you can see | [permissions.py:69](../zane_api/permissions.py#L69) | `get_accessible_projects()` and its async twin `aget_accessible_projects()` |

Two things about the existing code that shape this plan:

- **Every permission check ends up looking at the `WorkspaceMembership` table**, and each place does its own query. `has_min_role` is called from 5 places in [serializers.py](../zane_api/serializers.py), `get_accessible_projects` from about 25 places in the views. That is a lot of repeated queries for the same answer.
- **`request.workspace` is read in about 119 places.** So tokens must set `request.workspace` and a role just like sessions do. If they don't, we'd have to touch all 119 places.

---

## 2. The design — three separate questions

When a token makes a request, we ask three independent questions. **All three must pass.**

| Question | What it means | Answer for a logged-in user | Answer for a token |
| --- | --- | --- | --- |
| **Role** | How much power? | `membership.role` | the smaller of `token.role` and the creator's role |
| **Scope** | Which parts of the API? | no limit | `token.scopes` |
| **Project** | Which projects? | `membership.accessible_projects` | the token's projects, limited to the creator's projects |

Roles and scopes look similar but they are not. Role says *how much power*, scope says *which area*. A CI token typically wants Member-level power but **only** for deploying — nothing else. You can't say that with roles alone, and you can't say "can edit config" with scopes alone. You need both.

Logged-in users are not affected by any of this. They have no scopes, and the scope check simply does nothing for them.

### The `EffectiveAccess` cleanup (do this first)

Right now, the answer to "what can this request do?" is recomputed in ~30 different places. Before adding tokens, gather it into one object:

```python
@dataclass(frozen=True)
class EffectiveAccess:
    workspace: Workspace
    role: WorkspaceRole
    project_ids: QuerySet | None            # None = every project in the workspace
    scopes: frozenset[TokenScope] | None    # None = no scope limit (logged-in user)
    token: WorkspaceApiToken | None
```

`HasWorkspace` builds this **once** per request and stores it on `request.access`. Then `has_min_role`, the four `IsWorkspace*` classes and `get_accessible_projects` are changed to just read `request.access` instead of querying `WorkspaceMembership` again.

Two wins: fewer duplicate queries, and **one single place** where token auth can plug in a different answer.

Do this as its own PR with no token code in it. Otherwise the token PR is 90% find-and-replace edits and nobody can review it properly.

---

## 3. The model

Put it in **`zane_api/models/main.py`**, next to `WorkspaceMembership`. This is not an EE-only feature.

```python
class WorkspaceApiToken(TimestampedModel):
    id         = ShortUUIDField(length=11, prefix="tok_", primary_key=True)
    workspace  = FK(Workspace, on_delete=CASCADE, related_name="api_tokens")
    created_by = FK(AUTH_USER_MODEL, on_delete=CASCADE, related_name="api_tokens")

    name       = CharField(max_length=255)
    role       = PositiveSmallIntegerField(choices=WorkspaceRole.choices)
    scopes     = ArrayField(CharField(choices=TokenScope.choices))
    accessible_projects = M2M(Project, blank=True)   # empty = the whole workspace

    token_hash = CharField(max_length=64, unique=True, db_index=True)  # sha256 hex
    last_four  = CharField(max_length=4)             # just for display: zn_••••a1b2

    expires_at   = DateTimeField(null=True, blank=True)
    last_used_at = DateTimeField(null=True, blank=True)
    revoked_at   = DateTimeField(null=True, blank=True)
```

Notes:

- `on_delete=CASCADE` on `created_by`: delete the user, their tokens go too. That's what we want — see §4.
- `expires_at = None` means the token never expires. The UI should probably suggest 90 days by default.
- Revoking sets `revoked_at` instead of deleting the row, so the record still exists later for the audit feature.

---

## 4. A token can never do more than the person who made it

This is checked **on every request**, not just when the token is created:

```
role the token actually gets     = min(token.role, creator's current role)
projects the token actually gets = token's projects, limited to the creator's projects
```

If the creator is no longer a member of the workspace, the token stops working.

This is the most important rule here. Without it: a Member creates an Admin token, then leaves the company, and that token keeps full admin access forever. With it, removing someone from the workspace automatically weakens or kills every token they made — nobody has to remember to go clean them up.

The cost is one `WorkspaceMembership` query per token request. That's the same query `HasWorkspace` already runs for logged-in users, so it costs us nothing extra.

---

## 5. What a token looks like, and how we check it

Format: `zn_<token_id>_<secret>` — for example `zn_tok_a1b2c3d4e5f_kJ8x...`

```python
secret = secrets.token_urlsafe(32)
token_hash = hashlib.sha256(secret.encode()).hexdigest()
```

- **Why the id is inside the token:** we can look the row up directly by primary key, then check the secret against that one row. Without the id we'd have to hash the secret and scan for a match, which is slower and needs an extra index.
- **Why sha256 and not bcrypt/argon2:** those are for *passwords*, which are short and guessable, so they're made slow on purpose. Our secret is 32 random bytes — guessing it is not possible, so there is nothing to slow an attacker down. Making it slow would only slow down every legitimate request. Compare with `secrets.compare_digest` so the comparison takes the same time regardless of input.
- The full token is shown to the user **once**, right after creation, and never again — we only store the hash. Keep `last_four` so the UI can show which token is which.
- The `zn_` prefix is on purpose: secret scanners (GitHub push protection and similar) look for recognisable prefixes, so a leaked token can be spotted.

**`last_used_at`:** only update it if the stored value is more than ~5 minutes old. Otherwise every single API request turns into a database write.

---

## 6. Scopes

Scopes are named `resource:action`. `write` also gives you `read` on the same resource. Start small — once a scope name is public we're stuck with it.

| Scope | What it allows |
| --- | --- |
| `deploy:write` | Trigger deployments and preview environments, cancel, redeploy |
| `service:read` | Read service configuration and details |
| `service:write` | Create / update / delete services |
| `env:read` | Read environment variables (**sensitive** — see below) |
| `env:write` | Create / update / delete environment variables |
| `logs:read` | Runtime logs, build logs, metrics |
| `project:read` | List and read projects and environments |
| `project:write` | Create / update / delete projects and environments |

Rules:

- **`env:read` is never given automatically**, not even by `service:read`. Environment variables hold database passwords and API keys. Making people ask for it explicitly is the main reason scopes are worth building.
- Each view gets a `required_scopes: list[TokenScope]` attribute. Having **any one** of the listed scopes is enough. A new `HasRequiredScopes` permission class checks it, and does nothing when `request.access.scopes is None` (a logged-in user).
- **A view with no `required_scopes` cannot be reached by a token at all.** This is deliberate: if we forget to annotate a view, the result is that tokens get *denied*, not accidentally allowed. With ~137 routes, we will forget at least one, and this way the mistake is harmless.
- What you can ask for is limited by your role: a Viewer cannot create a token with `service:write`.

The list of which scope covers which route still has to be written. Use [ROUTES_PERMISSIONS.md](./ROUTES_PERMISSIONS.md) as the checklist.

---

## 7. Deploy webhooks — the main reason we're doing this

Three routes today take a secret **in the URL** and have no permission check at all:

| Route | View |
| --- | --- |
| `PUT /api/deploy-service/docker/{deploy_token}` | [deployments.py:130](../zane_api/views/deployments.py#L130) |
| `PUT /api/deploy-service/git/{deploy_token}` | [deployments.py:232](../zane_api/views/deployments.py#L232) |
| `POST /api/trigger-preview/{deploy_token}` | [environments.py:678](../zane_api/views/environments.py#L678) |

There's already a `# TODO: use an access token and filter by permission` sitting at [deployments.py:128](../zane_api/views/deployments.py#L128). And `deploy_token` is included in `ServiceSerializer`, which means a Viewer can read it off a service page and use it to deploy — a read-only user getting write access ([PERMISSIONS_CHANGELIST.md](./PERMISSIONS_CHANGELIST.md) §1).

**Decided: add a token requirement, keep the URLs.**

1. **The URLs don't change.** `deploy_token` stops being a secret and becomes just an id that identifies the service.
2. **Require** an `Authorization: Bearer zn_...` header with the `deploy:write` scope, plus the usual check that the token covers that service's project. `permission_classes` changes from `AllowAny` to the token check.
3. Secrets are no longer in URLs, so they stop showing up in proxy logs, browser history and CI job output.

Existing users keep their webhook URL and only need to add a header. That's a much easier upgrade than changing the URL, which is why we're not deprecating `deploy_token`.

This also fixes the Viewer problem by itself: once `deploy_token` isn't a secret, showing it to a Viewer doesn't matter — they still can't deploy without a token that has `deploy:write`.

### Later: use `service_id` in the URL instead

`Service` already has a proper public id — `id = ShortUUIDField(prefix=ID_PREFIX)` ([main.py:1462](../zane_api/models/main.py#L1462)) — plus a slug. Once `deploy_token` is no longer a secret, it's just a second id for the same thing, which is redundant. The routes should eventually take `service_id`.

Do that **in a separate PR, by adding rather than replacing**:

- Add `PUT /api/deploy-service/docker/{service_id}` next to the existing route.
- Keep the `deploy_token` routes working indefinitely. They cost one indexed lookup and break nobody.
- Only after that, consider dropping the `deploy_token` column and `POST .../regenerate-deploy-token` ([urls.py:353](../zane_api/urls.py#L353)).

No reason to mix this into the auth work.

**About `regenerate-deploy-token`:** once the Bearer header is required, this endpoint regenerates something that isn't a secret anymore. It still does something useful (old webhook URLs stop working), so it's a confusing name rather than a bug. Leave it alone for now; it goes away with the `service_id` change.

---

## 8. The authentication class

New file `zane_api/authentication.py` with `WorkspaceTokenAuthentication(BaseAuthentication)`, added to `DEFAULT_AUTHENTICATION_CLASSES` **after** `SessionAuthentication`.

```
Authorization: Bearer zn_tok_xxx_yyy
```

What it does:

- Returns `(user, token)`, so `request.user` is the person who created the token and `request.auth` is the token object.
- Rejects the request if: the id doesn't exist, the hash doesn't match, `revoked_at` is set, `expires_at` has passed, or the creator is no longer a member.
- Sets `request.workspace` from `token.workspace` and **ignores the session completely**. A token belongs to one workspace; there's no "switch workspace" for a token.
- Be careful with header parsing: if the scheme isn't `Bearer`, return `None` so other authentication classes get a turn. Only raise `AuthenticationFailed` if it *is* a `Bearer` header and the value is bad. Never let a malformed header cause a 500.

Making `request.user` the creator (instead of some anonymous token identity) is the cheap option, because `request.user` is used in ~119 places and this way none of them change. **The audit-trail side of this is deliberately not decided yet** — audit is a planned EE feature and can revisit whether a token should be its own identity. `request.auth` already holds the token, so attributing an action to a token later is possible.

---

## 9. Endpoints for managing tokens

New routes under `/api/workspace/tokens`:

| Route | Method | Who can use it |
| --- | --- | --- |
| `/api/workspace/tokens` | GET | your own tokens; Admin and above see all in the workspace |
| `/api/workspace/tokens` | POST | Member and above (limits below) — returns the full token **once** |
| `/api/workspace/tokens/{id}` | GET, PATCH | the token's creator, or Admin and above |
| `/api/workspace/tokens/{id}/revoke` | POST | the token's creator, or Admin and above |

What each role can create:

| Your role | Highest token role you can create | Projects |
| --- | --- | --- |
| Viewer | Viewer | only the projects you can access |
| Member | Member | any in the workspace |
| Admin | Admin | any |
| Owner | Owner | any |

Never above your own role. Check this in the serializer when creating, **and** again on every request (§4) — because you might get demoted after creating the token.

---

## 10. Things tokens must not be able to do

§6 already blocks these (no `required_scopes` means no token access), but write explicit tests for them:

- Instance-owner routes — auto-update, instance settings ([auto_update_docker_services.py:42](../zane_api/views/auto_update_docker_services.py#L42))
- Everything in [views/auth.py](../zane_api/views/auth.py) — login, logout, registration, changing password
- **Creating tokens.** A token must not be able to create another token, or a narrow short-lived token could be used to create a wide permanent one.
- Workspace invitations and changing members' roles
- **Webshell** ([webshell/consumers/](../webshell/consumers/)) — a shell is basically arbitrary code execution on the server. No token access in v1.

---

## 11. Async code and websockets

`aget_accessible_projects` needs the same `EffectiveAccess` change as the sync version.

The websocket consumers authenticate through Channels' session middleware, not through DRF, so they **won't** get token auth automatically. For webshell that's exactly what we want (§10). If we ever want a token-authenticated websocket (streaming logs, say), it needs its own deliberate implementation — not in this plan.

---

## 12. Other bits

- **Rate limiting** — add a `token` entry to `DEFAULT_THROTTLE_RATES`, higher than `anon` since CI tends to fire several requests at once. The existing `deploy_webhook` limit (60/min) stays as is.
- **OpenAPI** — add a drf-spectacular `OpenApiAuthenticationExtension` so the schema documents bearer auth, and mention each view's required scopes in its description. Then regenerate the frontend client with `pnpm gen:api`.
- **Frontend** — a token page in workspace settings: create (pick role, scopes, projects), show the token once with a copy button, list tokens with `last_used_at`, revoke.
- **Docs** — ship a copy-pasteable CI example. That's the whole point of the feature.

---

## 13. On purpose, not in this plan

- **`CONTRIBUTOR = 20`** ([main.py:85](../zane_api/models/main.py#L85)) — stays commented out. The "outside contractor" case is already covered by giving someone Member limited to two projects, and scopes now cover "can do X but not Y". Adding a fifth role means re-checking every `role >= X` comparison a second time, in a PR that's already touching all of them. Only add it if we find a capability set that roles + scopes genuinely can't express.
- **Audit trail** — separate EE feature. §8 notes the one decision it will want to revisit.
- **Token auth over websockets** — §11.
- **Per-service scopes** — v1 goes down to the project level, not individual services.

---

## 14. Order of work

Write tests first at each step.

1. **The `EffectiveAccess` cleanup**, with no token code. Change `has_min_role`, the `IsWorkspace*` classes and `get_accessible_projects` / `aget_accessible_projects` to read `request.access`. Nothing should behave differently — the existing permission tests must pass without being edited. Ship this on its own.
2. **Model + migration** — `WorkspaceApiToken`, the `TokenScope` enum, and the helpers that generate and verify tokens.
3. **The authentication class** — plus the token branch in `EffectiveAccess` and the "never above the creator" rule from §4.
4. **`HasRequiredScopes`**, then add `required_scopes` to every view. This is the big repetitive part; work through [ROUTES_PERMISSIONS.md](./ROUTES_PERMISSIONS.md).
5. **The management endpoints**, serializers, and the creation limits.
6. **Deploy webhooks** — require the Bearer header (§7). URLs stay the same; `deploy_token` stops being a secret.
7. **Regenerate OpenAPI + frontend UI + docs.**

A later, separate PR: `service_id` deploy routes (§7).

Step 1 should be its own PR; steps 2–6 can be one or several. **Step 4 is the risky one** — if we miss a view, that view just becomes unusable by tokens, which is annoying but safe (much better than accidentally leaving it open). Still, add a test that walks every registered route and asserts it either declares `required_scopes` or is on the explicit deny list.
