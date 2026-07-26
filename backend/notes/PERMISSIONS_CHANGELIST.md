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

| Capability | Drafted | Change to | Why |
|---|---|---|---|
| View logs (runtime, build, HTTP) | Viewer | **Member** | Apps print connection strings on startup failures; stack traces carry tokens; build logs echo build args and registry creds. Contradicts the env-var restriction one row below it. |
| List workspace members | Viewer | **Member** | An outsider doesn't need the team roster. Netlify's Reviewer doesn't get it. |
| View detected ports | Viewer | **Member** | *(minor)* Internal config detail, not product surface. Low impact — drop only if it's free. |

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

| Capability | Drafted | Change to |
|---|---|---|
| Git connectors — setup / create / edit / delete | Owner | **Admin** |
| Registry credentials — create / edit / delete | Owner | **Admin** |

Owner keeps only the irreversible and the financial: transfer ownership, delete workspace, edit workspace settings.

---

## 4. Confirm — shared env variables

The draft puts "Manage env variables" (environment-level) at **Member**; today write is **Admin** ([environments.py:589](../zane_api/views/environments.py#L589)). Shared env vars propagate to every service in the environment, so this widens the blast radius.

Consistent with Member managing service-level env vars, so probably deliberate — just confirming it isn't drift.

---

## 5. Building block for later — single deploy check

Deploy authorization is currently repeated as `permission_classes` across ~10 deploy / redeploy / toggle views. Collapsing it into one `can_deploy(user, service)` helper that those views call makes protected environments a one-function change later instead of ten edits.

No model change needed now. This is the only prerequisite worth paying for up front.

---

## 6. Explicitly deferred

- **Contributor role (20).** The slot stays commented out. Its only unique contribution was "deploys but can't read secrets", which is advisory anyway for git services — anyone who controls the code can print the environment to stdout. Revisit if a paying team asks.
- **Protected environments** (`Environment.is_protected`, Member deploys unprotected / Admin deploys protected). Right feature, wrong time — this is what every competitor uses for the prod gate, but small teams don't need it. Item 5 keeps it cheap to add.
- **EE-gating Viewer.** Render can put Viewer behind Scale+ because it sells to enterprises. The right comparable is Netlify's Reviewer: free and unlimited, because the point is inviting people who aren't on your team. Gating it kills the one role that earns its keep at this size.

---

## 7. UI labels — the important part

At this team size the invite dropdown does more enforcement than the permission classes. The failure mode is not privilege escalation, it's **someone picking the wrong role for their contractor**. A Viewer granted Member by mistake is the realistic incident.

Every role needs a one-line consequence, not a job title. Name what the role *cannot* do — that's the part people get wrong.

### Invite / role-picker copy

| Role | Label | Helper text |
|---|---|---|
| Viewer | **Viewer** — read-only | For clients, stakeholders and contractors. Can see your apps, their URLs and whether they're up. **Cannot see logs, environment variables, or deploy.** Limited to the projects you pick. |
| Member | **Member** — full access | For your team. Can create, configure and deploy services, and read all environment variables and logs. Cannot delete services or projects, or manage members. |
| Admin | **Admin** — manages the workspace | Everything a Member can do, plus deleting services and projects, managing environments, connectors and registries, and inviting people. |
| Owner | **Owner** | Owns the workspace and the server. Only the Owner can change workspace settings, transfer ownership or delete the workspace. |

### Rules

- **Default to Member.** Already the case ([main.py:122](../zane_api/models/main.py#L122)). Viewer must be a deliberate choice, never a default someone clicks past.
- **Viewer requires picking projects.** The project selector should be part of the invite flow, not a settings page visited afterwards — an unscoped Viewer is the accident this prevents.
- **Say "cannot" out loud on Viewer.** "Read-only" is not specific enough; people assume read-only includes logs. It doesn't, and that's the whole point of the tier.
- **Owner is not selectable.** It's reached only through transfer of ownership.
- **Show the role on the member list**, not just in the invite dialog. Misassignments are found by scanning the roster, not by re-opening an invite.
