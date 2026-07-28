# Permission Matrix — Changelist

Deltas from the drafted role matrix (Viewer 10 / Member 30 / Admin 40 / Owner 50). Only what changes is listed; everything not mentioned stays as drafted.

## Premise

ZaneOps' users today are solo devs and small teams. On a 3-person team everyone above Viewer is inside the trust circle — nobody is defending against their co-founder. That gives one design rule:

> **Only the Viewer ↔ Member boundary is a real security boundary.** Member / Admin / Owner are convenience and accident rails.

Consequences:

- Correctness budget goes to Viewer. Get `deploy_token`, logs and env vars right there.
- Member → Admin bypasses are papercuts, not incidents. Don't audit those edges.
- Viewer's only realistic occupant is an **outsider** — a client, a contractor, a designer. The "internal read-only on-call engineer" persona doesn't exist at this team size; that person is just an Admin.

---

## 1. Blocker — `deploy_token` leaks write access to Viewer

`deploy_token` is a field on `ServiceSerializer` ([serializers.py:494](../zane_api/serializers.py#L494), field at [:564](../zane_api/serializers.py#L564)), which backs service-details. The matrix grants Viewer "View details", and `PUT /api/deploy-service/docker/{deploy_token}` is `AllowAny` ([deployments.py:126](../zane_api/views/deployments.py#L126)) — same for the git and compose-stack webhooks.

A Viewer reads the token off the detail response and deploys. Read-only role, write access.

**Fix:** strip `deploy_token` from the serialized payload below Member. Not a policy call — the matrix is unenforceable without it.

---

## 2. Viewer — remove

| Capability                       | Drafted | Change to  | Why                                                                                                                                                                                |
| -------------------------------- | ------- | ---------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| View logs (runtime, build, HTTP) | Viewer  | **Member** | Apps print connection strings on startup failures; stack traces carry tokens; build logs echo build args and registry creds. Contradicts the env-var restriction one row below it. |
| List workspace members           | Viewer  | **Member** | An outsider doesn't need the team roster. Netlify's Reviewer doesn't get it.                                                                                                       |
| View detected ports              | Viewer  | **Member** | *(minor)* Internal config detail, not product surface. Low impact — drop only if it's free.                                                                                        |

Viewer **keeps** metrics and deployment status/history. That's the health signal without the payload, and it matches Render's Viewer, which gets events and metrics but explicitly no logs.

Precedent for the logs line: Heroku's `View` excludes logs *and* config vars (logs live in `Operate`); Render's Viewer excludes logs; Kubernetes' `view` ClusterRole excludes Secrets on escalation grounds. Every platform surveyed draws it the same way.

### Resulting Viewer surface

Scoped to `accessible_projects` throughout:

- Apps / services / stacks: name, public URLs, up-down status
- Deployments: list, detail, status, history
- Metrics
- Workspace: view details, switch, leave

Not: logs of any kind, env variables, deploy tokens, terminal, member list, config internals.

---

## 3. Owner → Admin — unblock routine infra config

Owner-only currently covers routine work. On a small team that means either the Owner gets pinged weekly or the team shares the Owner login — the second is what actually happens, and it's worse than granting the permission.

| Capability                                      | Drafted | Change to |
| ----------------------------------------------- | ------- | --------- |
| Git connectors — setup / create / edit / delete | Owner   | **Admin** |
| Registry credentials — create / edit / delete   | Owner   | **Admin** |

Owner keeps only the irreversible and the financial: transfer ownership, delete workspace, edit workspace settings.

**Applied.** Registry credential *creation* was Member rather than Owner ([credentials.py:24](../container_registry/views/credentials.py#L24)); it moved up to Admin so the whole row sits at one level. Listing stays Member — services reference credentials by id.

---

## 4. Confirm — shared env variables

The draft puts "Manage env variables" (environment-level) at **Member**; today write is **Admin** ([environments.py:589](../zane_api/views/environments.py#L589)). Shared env vars propagate to every service in the environment, so this widens the blast radius.

**Resolved: stays Admin.** The draft's Member was the drift; no code change.

---

## 5. Building block for later — single deploy check

**Deferred — nothing to do yet.** This ships as a pure no-op; its only value is making protected environments (§6) a one-function change instead of fourteen edits. Kept here so it isn't re-derived when that feature is scheduled.

> Since this was written, [`has_min_role(request, role)`](../zane_api/permissions.py#L58) landed for the field-level stripping in §1. That makes the `get_workspace_role()` helper below redundant — `can_deploy` becomes `return has_min_role(request, WorkspaceRole.MEMBER)`, and only the `environment` argument is new.

Deploy authorization is currently repeated as `permission_classes` across ~12 deploy / redeploy / toggle views. Collapsing it into one helper makes protected environments a one-function change later instead of twelve edits. No model change needed now.

**Constraint:** `permission_classes` runs *before* the object exists — `project` → `environment` → `service` are resolved inside `put()` ([docker_services.py:853](../zane_api/views/docker_services.py#L853)), and these are plain `APIView` handlers, so `has_object_permission()` never fires either. So this cannot be a `BasePermission`; it's a plain function called once the environment is in hand.

In [permissions.py](../zane_api/permissions.py), beside `get_accessible_projects`:

```python
def get_workspace_role(user: AbstractUser, workspace: Workspace) -> WorkspaceRole | None:
    membership = WorkspaceMembership.objects.filter(
        user=user, workspace=workspace
    ).first()
    return WorkspaceRole(membership.role) if membership is not None else None


def can_deploy(
    user: AbstractUser, workspace: Workspace, environment: Environment
) -> bool:
    role = get_workspace_role(user, workspace)
    if role is None:
        return False
    return role >= WorkspaceRole.MEMBER


def check_can_deploy(request: Request, environment: Environment) -> None:
    """Raises PermissionDenied (403) if the user may not deploy in this environment."""
    if not can_deploy(request.user, request.workspace, environment):
        raise PermissionDenied(
            "You do not have permission to deploy in this environment."
        )
```

`PermissionDenied` from `rest_framework.exceptions` → 403 with the message, no view-level error handling.

Call site is one line, after `environment` is resolved and before the service lookup:

```python
environment = Environment.objects.get(name=env_slug.lower(), project=project)
check_can_deploy(request, environment)
```

- `permission_classes = [HasWorkspace, IsWorkspaceMember]` **stays** — cheap early gate, so a Viewer 403s without hitting the service query. `check_can_deploy` layers after it.
- Identical to `IsWorkspaceMember` today, so it ships as a no-op. Protected envs later become two lines inside `can_deploy`: `if environment.is_protected: return role >= WorkspaceRole.ADMIN`.
- Takes `environment`, not `service` — lets services and compose stacks share one function without a union type, and it's already a local at every call site.
- **Call sites:** `Deploy{Docker,Git}ServiceAPIView`, `{Redeploy,ReDeploy}{Docker,Git}ServiceAPIView`, `BulkDeployServicesAPIView`, `CancelServiceDeploymentAPIView`, `{Toggle,BulkToggle}Service(s)APIView`, plus `ComposeStack{Deploy,ReDeploy}APIView`, `CancelComposeStackDeploymentAPIView`, `ToggleComposeStackAPIView`.
- **Webhooks need their own check.** The `{deploy_token}` routes are `AllowAny` with no user, so `can_deploy` doesn't apply — they need `can_deploy_with_token(environment)`, trivially `True` today, later `not environment.is_protected`. Without it the token bypasses the gate, same hole as §1.
- *Optional:* every permission class re-queries `WorkspaceMembership` independently ([permissions.py:109](../zane_api/permissions.py#L109), [:121](../zane_api/permissions.py#L121), [:133](../zane_api/permissions.py#L133), [:145](../zane_api/permissions.py#L145)) and this adds one more. `HasWorkspace` runs first on all these routes and could stash the membership on `request` for the rest to read — separate change, removes a duplicate query per authenticated request.

---

## 6. Explicitly deferred

- **Contributor role (20).** The slot stays commented out. Its only unique contribution was "deploys but can't read secrets", which is advisory anyway for git services — anyone who controls the code can print the environment to stdout. Revisit if a paying team asks.
- **Protected environments** (`Environment.is_protected`, Member deploys unprotected / Admin deploys protected). Right feature, wrong time — this is what every competitor uses for the prod gate, but small teams don't need it. Item 5 keeps it cheap to add.

---

## 7. UI labels — the important part

**Applied.**

At this team size the invite dropdown does more enforcement than the permission classes. The failure mode is not privilege escalation, it's **someone picking the wrong role for their contractor**. A Viewer granted Member by mistake is the realistic incident.

Every role needs a one-line consequence, not a job title. Name what the role *cannot* do — that's the part people get wrong.

### Invite / role-picker copy

| Role   | Label                             | Helper text                                                                                                                                                                               |
| ------ | --------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Viewer | **Viewer** — read-only            | For clients, stakeholders and contractors. Can see your apps, their URLs and whether they're up. **Cannot see logs, environment variables, or deploy.** Limited to the projects you pick. |
| Member | **Member** — full access          | For your team. Can create, configure and deploy services, and read all environment variables and logs. Cannot delete services or projects, or manage members.                             |
| Admin  | **Admin** — manages the workspace | Everything a Member can do, plus deleting services and projects, managing environments, connectors and registries, and inviting people.                                                   |
| Owner  | **Owner**                         | Full control of the workspace. Only the Owner can change workspace settings, transfer ownership or delete the workspace. Reached through transfer of ownership, not by being assigned.    |

### Rules

- **Default to Member.** Already the case on the model ([main.py:122](../zane_api/models/main.py#L122)) — but the invite form defaulted its dropdown to **Viewer**, so every invite started on the wrong tier. Fixed.
- **Viewer requires picking projects.** The project selector should be part of the invite flow, not a settings page visited afterwards — an unscoped Viewer is the accident this prevents.
- **Say "cannot" out loud on Viewer.** "Read-only" is not specific enough; people assume read-only includes logs. It doesn't, and that's the whole point of the tier.
- **Owner is not selectable.** It's reached only through transfer of ownership. Note the draft copy said the Owner "owns the workspace and the server" — that is wrong. Server admin is `is_superuser` / `IsInstanceOwner`, entirely separate from `WorkspaceRole.OWNER`, and [transfer-ownership](../zane_api/views/workspace.py#L481) only flips the membership role. In practice the first Owner is usually also the superuser, but nothing enforces it and a transfer breaks the overlap.
- **Show the role on the member list**, not just in the invite dialog. Misassignments are found by scanning the roster, not by re-opening an invite. Already there — the members table has a Role column.
- **Viewer requires picking projects** was already satisfied: the project multi-select appears inline in both the invite and edit-permissions forms when Viewer is selected, and the backend rejects an empty list ([serializers/workspace.py:78](../zane_api/views/serializers/workspace.py#L78)).

Copy lives on `WORKSPACE_ROLE_MAPPING` ([constants.tsx:202](../../frontend/app/lib/constants.tsx#L202)), alongside each role's numeric value so there is a single constant describing roles — a `summary` shown beside the role name in the dropdown, and a `description` shown under the picker for the selected role and in a tooltip on the members table role badges. The forms render it inline rather than sharing a component.

---

## 8. Frontend route guards — out of sync with the backend

Worth its own section rather than folding into §7: only part of it is mechanical, and the non-mechanical part is a hole rather than an annoyance.

`ensureMinRole()` throws `notFound()` ([queries.ts:99](../../frontend/app/lib/queries.ts#L99)), so a guard that is too strict shows a **404**, not a 403. A user who genuinely has the permission is told the page does not exist — which reads as a bug, not as a permission error.

### 8a. Guards still asking for Owner *(mechanical)*

§3 moved these to Admin on the backend; the frontend still gates them at Owner, so an Admin gets a 404 on a page they can now use.

| Route | Should be |
|---|---|
| `settings/git-apps-list.tsx:45` | Admin |
| `settings/create-github-app.tsx:29` | Admin |
| `settings/create-gitlab-app.tsx:32` | Admin |
| `settings/gitlab-app-details.tsx:33` | Admin |
| `settings/create-registry-credentials.tsx:47` | Admin |
| `settings/registry-credentials-details.tsx:57` | Admin |
| `settings/registry-credentials-list.tsx:50` | **Member** — listing stayed Member, only create/edit/delete are Admin |
| `services/create-private-git-service.tsx:106` | Admin — `hasMinRole`, gates the "set up a connector" branch |

Note the list route is the odd one out: copying Admin everywhere would wrongly hide the credential list from Members who need to pick one when creating a service.

### 8b. Guards still asking for Member *(not mechanical)*

§2 granted the Viewer a real surface, but the frontend still assumes Viewer sees nothing. [workspace-layout.tsx:33](../../frontend/app/routes/layouts/workspace-layout.tsx#L33) skips the project list entirely unless `hasMinRole(user, "Member")`, and the nav tab sets in `deployment-layout`, `environment-layout` and `project-settings-layout` are Member-gated as a block.

So a Viewer today logs in to an empty shell, even though the backend now serves them projects, services, stacks, deployments and metrics. Deciding what that UI *is* — which tabs survive, what a service detail page looks like with env vars and logs removed — is design work, not a guard swap. The dedicated `/workspace/viewer` route that used to stand in for this is gone.

The rule to apply per route: **Viewer** for anything the backend now serves them (project list, service list and details, deployments, metrics, stacks); **Member** for logs, env variables, detected ports, terminal and the member list.

### 8c. Unrelated but adjacent

`hasMinRole` logs the full membership object to the browser console on every call ([utils.ts:634](../../frontend/app/lib/utils.ts#L634)). Leftover debugging — should go.
