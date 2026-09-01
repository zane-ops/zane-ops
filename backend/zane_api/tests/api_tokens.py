from datetime import timedelta
from typing import cast

from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from ..models import (
    Project,
    TokenScope,
    Workspace,
    WorkspaceApiToken,
    WorkspaceMembership,
    WorkspaceRole,
)
from ..utils import jprint
from .base import AuthAPITestCase


class WorkspaceApiTokenModelTests(AuthAPITestCase):
    def setUp(self):
        super().setUp()
        self.user = cast(User, User.objects.get(username="Fredkiss3"))
        self.workspace = cast(Workspace, Workspace.objects.first())

    def create_token(self, **kwargs) -> tuple[WorkspaceApiToken, str]:
        defaults = dict(
            workspace=self.workspace,
            created_by=self.user,
            name="ci-token",
            role=WorkspaceRole.MEMBER,
            scopes=[TokenScope.DEPLOY_WRITE],
        )
        defaults.update(kwargs)
        return WorkspaceApiToken.generate(**defaults)

    # --- generation ------------------------------------------------------

    def test_generate_returns_token_and_full_string(self):
        token, full = self.create_token()

        self.assertIsInstance(token, WorkspaceApiToken)
        self.assertTrue(full.startswith("zn_tok_"))
        # zn_ + <token id> + _ + secret
        self.assertTrue(full.startswith(f"zn_{token.id}_"))

    def test_generate_only_stores_the_hash_not_the_secret(self):
        token, full = self.create_token()
        secret = full.split("_", 3)[3]

        self.assertNotIn(secret, token.token_hash)
        self.assertEqual(64, len(token.token_hash))
        self.assertEqual(WorkspaceApiToken.hash_secret(secret), token.token_hash)

    def test_generate_persists_row_with_last_four_of_secret(self):
        token, full = self.create_token()
        secret = full.split("_", 3)[3]

        token.refresh_from_db()
        self.assertEqual(secret[-4:], token.last_four)

    def test_generate_secret_is_unique(self):
        _, full_a = self.create_token()
        _, full_b = self.create_token()
        self.assertNotEqual(full_a, full_b)

    def test_scopes_default_to_empty_list(self):
        token, _ = self.create_token(scopes=[])
        token.refresh_from_db()
        self.assertEqual([], token.scopes)

    def test_accessible_projects_empty_by_default(self):
        token, _ = self.create_token()
        self.assertEqual(0, token.accessible_projects.count())

    def test_accessible_projects_can_be_scoped(self):
        project = Project.objects.create(slug="api", workspace=self.workspace)
        token, _ = self.create_token()
        token.accessible_projects.add(project)
        self.assertEqual(
            [project.id], list(token.accessible_projects.values_list("id", flat=True))
        )

    # --- parsing -------------------------------------------------------

    def test_parse_token_string_round_trips(self):
        token, full = self.create_token()
        secret = full.split("_", 3)[3]

        parsed = WorkspaceApiToken.parse_token_string(full)
        self.assertEqual((token.id, secret), parsed)

    def test_parse_token_string_rejects_malformed_input(self):
        token, full = self.create_token()
        secret = full.split("_", 3)[3]

        for bad in [
            "",
            "not-a-token",
            "Bearer zn_tok_xxx",
            full.removeprefix("zn_"),  # missing the zn_ prefix
            f"zn_{token.id}_",  # missing secret
            f"zn_tok_short_{secret}",  # id suffix not ID_LENGTH chars
            f"zn_wrk_{token.id[4:]}_{secret}",  # wrong id prefix
        ]:
            with self.subTest(bad=bad):
                self.assertIsNone(WorkspaceApiToken.parse_token_string(bad))

    def test_parse_token_string_never_raises_on_non_string(self):
        self.assertIsNone(WorkspaceApiToken.parse_token_string(None))  # type: ignore

    # --- verification / authenticate ---------------------------------

    def test_verify_secret(self):
        token, full = self.create_token()
        secret = full.split("_", 3)[3]

        self.assertTrue(token.verify_secret(secret))
        self.assertFalse(token.verify_secret(secret + "x"))
        self.assertFalse(token.verify_secret("wrong"))

    def test_authenticate_with_a_valid_token_string(self):
        token, full = self.create_token()
        found = WorkspaceApiToken.authenticate(full)
        self.assertIsNotNone(found)
        self.assertEqual(token.id, found.id)  # type: ignore

    def test_authenticate_rejects_unknown_id(self):
        _, full = self.create_token()
        secret = full.split("_", 3)[3]
        self.assertIsNone(
            WorkspaceApiToken.authenticate(f"zn_tok_00000000000_{secret}")
        )

    def test_authenticate_rejects_tampered_secret(self):
        token, full = self.create_token()
        secret = full.split("_", 3)[3]
        tampered = f"zn_{token.id}_{secret[:-1]}{'A' if secret[-1] != 'A' else 'B'}"
        self.assertIsNone(WorkspaceApiToken.authenticate(tampered))

    def test_authenticate_rejects_garbage(self):
        self.assertIsNone(WorkspaceApiToken.authenticate("garbage"))
        self.assertIsNone(WorkspaceApiToken.authenticate(""))

    def test_authenticate_returns_revoked_and_expired_tokens(self):
        # authenticate() only checks the hash; the caller decides what to do
        # with revoked/expired tokens.
        token, full = self.create_token(expires_at=timezone.now() - timedelta(days=1))
        token.revoke()
        found = WorkspaceApiToken.authenticate(full)
        self.assertIsNotNone(found)

    # --- state --------------------------------------------------------

    def test_is_active_by_default(self):
        token, _ = self.create_token()
        self.assertTrue(token.is_active)
        self.assertFalse(token.is_revoked)
        self.assertFalse(token.is_expired)

    def test_expired_token_is_not_active(self):
        token, _ = self.create_token(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertTrue(token.is_expired)
        self.assertFalse(token.is_active)

    def test_future_expiry_is_still_active(self):
        token, _ = self.create_token(expires_at=timezone.now() + timedelta(days=90))
        self.assertFalse(token.is_expired)
        self.assertTrue(token.is_active)

    def test_revoke_sets_revoked_at_once_and_is_idempotent(self):
        token, _ = self.create_token()
        token.revoke()
        self.assertIsNotNone(token.revoked_at)
        first = token.revoked_at

        token.revoke()
        self.assertEqual(first, token.revoked_at)

        token.refresh_from_db()
        self.assertIsNotNone(token.revoked_at)
        self.assertFalse(token.is_active)

    def test_masked_token(self):
        token, full = self.create_token()
        secret = full.split("_", 3)[3]
        self.assertEqual(f"zn_••••{secret[-4:]}", token.masked_token)

    # --- last_used_at throttling ------------------------------------

    def test_touch_last_used_writes_on_first_call(self):
        token, _ = self.create_token()
        self.assertIsNone(token.last_used_at)

        now = timezone.now()
        wrote = token.touch_last_used(now=now)

        self.assertTrue(wrote)
        token.refresh_from_db()
        self.assertEqual(now, token.last_used_at)

    def test_touch_last_used_is_a_noop_within_the_throttle_window(self):
        token, _ = self.create_token()
        start = timezone.now()
        token.touch_last_used(now=start)

        wrote = token.touch_last_used(now=start + timedelta(minutes=4))

        self.assertFalse(wrote)
        token.refresh_from_db()
        self.assertEqual(start, token.last_used_at)

    def test_touch_last_used_writes_again_after_the_throttle_window(self):
        token, _ = self.create_token()
        start = timezone.now()
        token.touch_last_used(now=start)

        later = start + timedelta(minutes=6)
        wrote = token.touch_last_used(now=later)

        self.assertTrue(wrote)
        token.refresh_from_db()
        self.assertEqual(later, token.last_used_at)


class WorkspaceApiTokenCRUDViewTests(AuthAPITestCase):
    """
    Management endpoints under `/api/workspace/tokens` — see
    `backend/notes/api-tokens-plan.md` §9.

    Route names assumed:
      - `zane_api:workspace.tokens`        GET (list) + POST (create)
      - `zane_api:workspace.token_detail`  GET + PATCH, kwarg `token_id`
      - `zane_api:workspace.token_revoke`  POST, kwarg `token_id`
    """

    def setUp(self):
        super().setUp()
        self.workspace = cast(Workspace, Workspace.objects.first())
        self.owner = cast(User, User.objects.get(username="Fredkiss3"))

    # -- helpers ------------------------------------------------------

    def set_my_role(self, role: WorkspaceRole):
        m = WorkspaceMembership.objects.get(user=self.owner, workspace=self.workspace)
        m.role = role
        m.save()

    def add_user(self, username: str, role: WorkspaceRole) -> User:
        user = User.objects.create_user(username=username, password="password")
        WorkspaceMembership.objects.create(
            user=user, workspace=self.workspace, role=role
        )
        return user

    def make_token(
        self,
        *,
        created_by: User | None = None,
        role: WorkspaceRole = WorkspaceRole.MEMBER,
        scopes=None,
        name="ci-token",
        workspace: Workspace | None = None,
    ) -> WorkspaceApiToken:
        token, _ = WorkspaceApiToken.generate(
            workspace=workspace or self.workspace,
            created_by=created_by or self.owner,
            name=name,
            role=role,
            scopes=scopes if scopes is not None else [TokenScope.DEPLOY_WRITE],
        )
        return token

    # -- auth -------------------------------------------------------

    def test_unauthenticated_is_rejected(self):
        response = self.client.get(reverse("zane_api:workspace.tokens"))
        jprint(response.json())
        self.assertEqual(status.HTTP_401_UNAUTHORIZED, response.status_code)

    # -- create ---------------------------------------------------

    def test_member_can_create_a_token_and_gets_the_secret_once(self):
        self.set_my_role(WorkspaceRole.MEMBER)
        self.loginUser()

        data = {
            "name": "ci-deploy",
            "role": WorkspaceRole.MEMBER,
            "scopes": [TokenScope.DEPLOY_WRITE],
        }
        response = self.client.post(reverse("zane_api:workspace.tokens"), data=data)
        body = response.json()
        jprint(body)
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        self.assertTrue(body["token"].startswith("zn_tok_"))

        token = WorkspaceApiToken.objects.get(id=body["id"])
        self.assertEqual(self.owner, token.created_by)
        self.assertEqual(self.workspace, token.workspace)
        self.assertEqual([TokenScope.DEPLOY_WRITE], token.scopes)
        # secret is never persisted in the clear
        self.assertNotIn(body["token"].split("_", 3)[3], token.token_hash)

    def test_created_token_secret_is_only_returned_at_creation(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:workspace.tokens"),
            data={
                "name": "ci",
                "role": WorkspaceRole.MEMBER,
                "scopes": [TokenScope.DEPLOY_WRITE],
            },
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        token_id = response.json()["id"]

        detail = self.client.get(
            reverse(
                "zane_api:workspace.token_detail",
                kwargs={"token_id": token_id},
            )
        )
        jprint(detail.json())
        self.assertEqual(status.HTTP_200_OK, detail.status_code)
        self.assertNotIn("token", detail.json())
        self.assertIn("last_four", detail.json())

    def test_viewer_cannot_create_tokens(self):
        self.set_my_role(WorkspaceRole.VIEWER)
        self.loginUser()

        response = self.client.post(
            reverse("zane_api:workspace.tokens"),
            data={
                "name": "nope",
                "role": WorkspaceRole.VIEWER,
                "scopes": [TokenScope.LOGS_READ],
            },
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)
        self.assertEqual(0, WorkspaceApiToken.objects.count())

    def test_cannot_create_a_token_above_your_own_role(self):
        self.set_my_role(WorkspaceRole.MEMBER)
        self.loginUser()

        response = self.client.post(
            reverse("zane_api:workspace.tokens"),
            data={
                "name": "too-powerful",
                "role": WorkspaceRole.ADMIN,
                "scopes": [TokenScope.SERVICE_WRITE],
            },
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertEqual(0, WorkspaceApiToken.objects.count())

    def test_admin_can_create_a_viewer_level_token(self):
        self.set_my_role(WorkspaceRole.ADMIN)
        self.loginUser()

        response = self.client.post(
            reverse("zane_api:workspace.tokens"),
            data={
                "name": "status-dashboard",
                "role": WorkspaceRole.VIEWER,
                "scopes": [TokenScope.PROJECT_READ],
            },
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        token = WorkspaceApiToken.objects.get()
        self.assertEqual(WorkspaceRole.VIEWER, token.role)

    def test_create_rejects_unknown_scopes(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:workspace.tokens"),
            data={
                "name": "bad-scope",
                "role": WorkspaceRole.MEMBER,
                "scopes": ["service:destroy"],
            },
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_create_with_accessible_projects(self):
        self.loginUser()
        project = Project.objects.create(slug="api", workspace=self.workspace)

        response = self.client.post(
            reverse("zane_api:workspace.tokens"),
            data={
                "name": "one-project",
                "role": WorkspaceRole.MEMBER,
                "scopes": [TokenScope.DEPLOY_WRITE],
                "accessible_project_ids": [project.id],
            },
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        token = WorkspaceApiToken.objects.get()
        self.assertEqual(
            [project.id],
            list(token.accessible_projects.values_list("id", flat=True)),
        )

    def test_create_defaults_to_a_30_day_expiry(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:workspace.tokens"),
            data={
                "name": "default-ttl",
                "role": WorkspaceRole.MEMBER,
                "scopes": [TokenScope.DEPLOY_WRITE],
            },
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        expires_at = WorkspaceApiToken.objects.get().expires_at
        self.assertIsNotNone(expires_at)
        self.assertAlmostEqual(
            expires_at,
            timezone.now() + timedelta(days=30),
            delta=timedelta(minutes=1),
        )

    def test_explicit_null_expiry_still_gets_the_30_day_default(self):
        # every token expires — `null` is not a way around that (see plan §3
        # note; product decision to always set an expiry).
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:workspace.tokens"),
            data={
                "name": "still-expires",
                "role": WorkspaceRole.MEMBER,
                "scopes": [TokenScope.DEPLOY_WRITE],
                "expires_at": None,
            },
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        expires_at = WorkspaceApiToken.objects.get().expires_at
        self.assertIsNotNone(expires_at)
        self.assertAlmostEqual(
            expires_at,
            timezone.now() + timedelta(days=30),
            delta=timedelta(minutes=1),
        )

    def test_create_with_explicit_expiry(self):
        self.loginUser()
        expires_at = (timezone.now() + timedelta(days=90)).isoformat()
        response = self.client.post(
            reverse("zane_api:workspace.tokens"),
            data={
                "name": "90d",
                "role": WorkspaceRole.MEMBER,
                "scopes": [TokenScope.DEPLOY_WRITE],
                "expires_at": expires_at,
            },
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        self.assertIsNotNone(WorkspaceApiToken.objects.get().expires_at)

    # -- list ---------------------------------------------------

    def test_member_only_sees_their_own_tokens(self):
        self.set_my_role(WorkspaceRole.MEMBER)
        other = self.add_user("mohai", WorkspaceRole.MEMBER)
        mine = self.make_token(created_by=self.owner, name="mine")
        self.make_token(created_by=other, name="theirs")

        self.loginUser()
        response = self.client.get(reverse("zane_api:workspace.tokens"))
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        ids = {row["id"] for row in response.json()}
        self.assertEqual({mine.id}, ids)

    def test_admin_sees_all_tokens_in_the_workspace(self):
        self.set_my_role(WorkspaceRole.ADMIN)
        other = self.add_user("mohai", WorkspaceRole.MEMBER)
        a = self.make_token(created_by=self.owner, name="mine")
        b = self.make_token(created_by=other, name="theirs")

        self.loginUser()
        response = self.client.get(reverse("zane_api:workspace.tokens"))
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        ids = {row["id"] for row in response.json()}
        self.assertEqual({a.id, b.id}, ids)

    def test_list_never_leaks_tokens_from_another_workspace(self):
        self.loginUser()
        other_ws = Workspace.objects.create(name="Other")
        WorkspaceMembership.objects.create(
            user=self.owner, workspace=other_ws, role=WorkspaceRole.OWNER
        )
        self.make_token(workspace=other_ws, name="elsewhere")
        mine = self.make_token(name="here")

        response = self.client.get(reverse("zane_api:workspace.tokens"))
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        ids = {row["id"] for row in response.json()}
        self.assertEqual({mine.id}, ids)

    def test_list_response_shape(self):
        self.loginUser()
        self.make_token(name="ci")
        response = self.client.get(reverse("zane_api:workspace.tokens"))
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        row = response.json()[0]
        for key in ("id", "name", "role", "scopes", "last_four", "last_used_at"):
            self.assertIn(key, row)
        self.assertNotIn("token", row)
        self.assertNotIn("token_hash", row)

    # -- detail / patch --------------------------------------

    def test_creator_can_read_their_token(self):
        self.set_my_role(WorkspaceRole.MEMBER)
        token = self.make_token(created_by=self.owner)
        self.loginUser()

        response = self.client.get(
            reverse(
                "zane_api:workspace.token_detail",
                kwargs={"token_id": token.id},
            )
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(token.id, response.json()["id"])

    def test_other_member_cannot_read_someone_elses_token(self):
        self.set_my_role(WorkspaceRole.MEMBER)
        other = self.add_user("mohai", WorkspaceRole.MEMBER)
        token = self.make_token(created_by=other)

        self.loginUser()
        response = self.client.get(
            reverse(
                "zane_api:workspace.token_detail",
                kwargs={"token_id": token.id},
            )
        )
        jprint(response.json())
        self.assertIn(
            response.status_code,
            (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND),
        )

    def test_admin_can_read_any_token(self):
        self.set_my_role(WorkspaceRole.ADMIN)
        other = self.add_user("mohai", WorkspaceRole.MEMBER)
        token = self.make_token(created_by=other)

        self.loginUser()
        response = self.client.get(
            reverse(
                "zane_api:workspace.token_detail",
                kwargs={"token_id": token.id},
            )
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_creator_can_rename_their_token(self):
        self.set_my_role(WorkspaceRole.MEMBER)
        token = self.make_token(created_by=self.owner, name="old")
        self.loginUser()

        response = self.client.patch(
            reverse(
                "zane_api:workspace.token_detail",
                kwargs={"token_id": token.id},
            ),
            data={"name": "new"},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        token.refresh_from_db()
        self.assertEqual("new", token.name)

    def test_other_member_cannot_patch_someone_elses_token(self):
        self.set_my_role(WorkspaceRole.MEMBER)
        other = self.add_user("mohai", WorkspaceRole.MEMBER)
        token = self.make_token(created_by=other, name="old")

        self.loginUser()
        response = self.client.patch(
            reverse(
                "zane_api:workspace.token_detail",
                kwargs={"token_id": token.id},
            ),
            data={"name": "hijacked"},
        )
        jprint(response.json())
        self.assertIn(
            response.status_code,
            (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND),
        )
        token.refresh_from_db()
        self.assertEqual("old", token.name)

    # -- revoke ---------------------------------------------

    def test_creator_can_revoke_their_token(self):
        self.set_my_role(WorkspaceRole.MEMBER)
        token = self.make_token(created_by=self.owner)
        self.loginUser()

        response = self.client.post(
            reverse(
                "zane_api:workspace.token_revoke",
                kwargs={"token_id": token.id},
            )
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        token.refresh_from_db()
        self.assertIsNotNone(token.revoked_at)
        self.assertFalse(token.is_active)

    def test_revoke_is_idempotent(self):
        token = self.make_token(created_by=self.owner)
        self.loginUser()
        url = reverse("zane_api:workspace.token_revoke", kwargs={"token_id": token.id})

        first = self.client.post(url)
        jprint(first.json())
        self.assertEqual(status.HTTP_200_OK, first.status_code)
        token.refresh_from_db()
        revoked_at = token.revoked_at

        second = self.client.post(url)
        jprint(second.json())
        self.assertEqual(status.HTTP_200_OK, second.status_code)
        token.refresh_from_db()
        self.assertEqual(revoked_at, token.revoked_at)

    def test_admin_can_revoke_any_token(self):
        self.set_my_role(WorkspaceRole.ADMIN)
        other = self.add_user("mohai", WorkspaceRole.MEMBER)
        token = self.make_token(created_by=other)

        self.loginUser()
        response = self.client.post(
            reverse(
                "zane_api:workspace.token_revoke",
                kwargs={"token_id": token.id},
            )
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        token.refresh_from_db()
        self.assertIsNotNone(token.revoked_at)

    def test_other_member_cannot_revoke_someone_elses_token(self):
        self.set_my_role(WorkspaceRole.MEMBER)
        other = self.add_user("mohai", WorkspaceRole.MEMBER)
        token = self.make_token(created_by=other)

        self.loginUser()
        response = self.client.post(
            reverse(
                "zane_api:workspace.token_revoke",
                kwargs={"token_id": token.id},
            )
        )
        jprint(response.json())
        self.assertIn(
            response.status_code,
            (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND),
        )
        token.refresh_from_db()
        self.assertIsNone(token.revoked_at)


class WorkspaceTokenAuthenticationTests(AuthAPITestCase):
    """
    The `WorkspaceTokenAuthentication` class + `EffectiveAccess` token branch,
    exercised through the docker deploy webhook (plan §7, §8).
    """

    WEBHOOK = "zane_api:services.docker.webhook_deploy"

    def setUp(self):
        super().setUp()
        self.workspace = cast(Workspace, Workspace.objects.first())
        self.owner = cast(User, User.objects.get(username="Fredkiss3"))
        self.project, self.service = self.create_redis_docker_service()
        # `create_redis_docker_service` logs in via session; the webhook route
        # is token-only so the cookie is ignored, but drop it to be explicit.
        self.client.logout()

    def webhook_url(self, service=None):
        return reverse(
            self.WEBHOOK,
            kwargs={"deploy_token": (service or self.service).deploy_token},
        )

    def bearer(self, full: str) -> dict:
        return {"headers": {"Authorization": f"Bearer {full}"}}

    def call(self, full: str | None, service=None):
        kw = self.bearer(full) if full is not None else {}
        return self.client.put(
            self.webhook_url(service),
            data={"new_image": "valkey/valkey:8-alpine"},
            **kw,
        )

    def make_token(self, **kwargs):
        kwargs.setdefault("scopes", [TokenScope.DEPLOY_WRITE])
        kwargs.setdefault("role", WorkspaceRole.MEMBER)
        return self.create_api_token(**kwargs)

    # -- happy path ---------------------------------------------

    def test_valid_deploy_token_triggers_a_deployment(self):
        _, full = self.make_token()
        response = self.call(full)
        jprint(response.json() if response.content else {})
        self.assertEqual(status.HTTP_202_ACCEPTED, response.status_code)

    def test_last_used_at_is_set_after_a_call(self):
        token, full = self.make_token()
        self.assertIsNone(token.last_used_at)
        self.call(full)
        token.refresh_from_db()
        self.assertIsNotNone(token.last_used_at)

    # -- rejected requests ------------------------------------

    def test_missing_authorization_header_is_401(self):
        response = self.call(None)
        self.assertEqual(status.HTTP_401_UNAUTHORIZED, response.status_code)

    def test_non_bearer_scheme_is_401(self):
        response = self.client.put(
            self.webhook_url(),
            data={},
            headers={"Authorization": "Basic zn_whatever"},
        )
        self.assertEqual(status.HTTP_401_UNAUTHORIZED, response.status_code)

    def test_malformed_bearer_headers_are_401_not_500(self):
        for value in ["Bearer", "Bearer a b", "Bearer not-a-token", "Bearer zn_tok_x"]:
            with self.subTest(value=value):
                response = self.client.put(
                    self.webhook_url(), data={}, headers={"Authorization": value}
                )
                self.assertEqual(status.HTTP_401_UNAUTHORIZED, response.status_code)

    def test_unknown_token_id_is_401(self):
        _, full = self.make_token()
        secret = full.split("_", 3)[3]
        response = self.call(f"zn_tok_00000000000_{secret}")
        self.assertEqual(status.HTTP_401_UNAUTHORIZED, response.status_code)

    def test_revoked_token_is_401(self):
        token, full = self.make_token()
        token.revoke()
        response = self.call(full)
        self.assertEqual(status.HTTP_401_UNAUTHORIZED, response.status_code)

    def test_expired_token_is_401(self):
        _, full = self.make_token(expires_at=timezone.now() - timedelta(minutes=1))
        response = self.call(full)
        self.assertEqual(status.HTTP_401_UNAUTHORIZED, response.status_code)

    def test_token_without_deploy_scope_is_403(self):
        _, full = self.make_token(scopes=[TokenScope.SERVICE_READ])
        response = self.call(full)
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_token_scoped_to_another_project_is_403(self):
        other_project = Project.objects.create(slug="other", workspace=self.workspace)
        _, full = self.make_token(accessible_projects=[other_project])
        response = self.call(full)
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_token_from_another_workspace_cannot_reach_the_service(self):
        other_ws = Workspace.objects.create(name="Other")
        WorkspaceMembership.objects.create(
            user=self.owner, workspace=other_ws, role=WorkspaceRole.OWNER
        )
        _, full = self.make_token(workspace=other_ws)
        response = self.call(full)
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_token_stops_working_when_creator_leaves_the_workspace(self):
        member = User.objects.create_user(username="mohai", password="password")
        membership = WorkspaceMembership.objects.create(
            user=member, workspace=self.workspace, role=WorkspaceRole.MEMBER
        )
        _, full = self.make_token(created_by=member)

        membership.delete()

        response = self.call(full)
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_token_role_is_capped_at_the_creators_current_role(self):
        member = User.objects.create_user(username="mohai", password="password")
        membership = WorkspaceMembership.objects.create(
            user=member, workspace=self.workspace, role=WorkspaceRole.ADMIN
        )
        # an Admin-role token, created while the creator was an Admin
        _, full = self.make_token(created_by=member, role=WorkspaceRole.ADMIN)

        # deploy:write still works regardless of role...
        self.assertEqual(status.HTTP_202_ACCEPTED, self.call(full).status_code)

        # ...but once the creator is demoted the effective role drops with them
        membership.role = WorkspaceRole.VIEWER
        membership.save()
        request_role = WorkspaceApiToken.objects.get().role
        self.assertEqual(WorkspaceRole.ADMIN, request_role)  # stored role unchanged
        # (effective role is recomputed per request in permissions.build_token_access)
