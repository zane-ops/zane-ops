import re
from typing import cast
from django.conf import settings
from django.urls import reverse
from rest_framework import status

from zane_api.tests.base import AuthAPITestCase
from zane_api.utils import generate_random_chars, jprint
import responses
from zane_api.models import GitApp, Deployment
from ..models import GitHubApp
from ..serializers import GithubWebhookEvent
from .github import (
    MANIFEST_DATA,
    INSTALLATION_CREATED_WEBHOOK_DATA,
    get_signed_event_headers,
)


GITHUB_PUSH_WEBHOOK_EVENT_DATA = {
    "ref": "refs/heads/main",
    "before": "e0522b4784bd16e2e10707fab1081b55f615158d",
    "after": "1c4801f2367acc933760f68e3e611cb2fd1b630d",
    "repository": {
        "id": 1012001150,
        "node_id": "R_kgDOPFHpfg",
        "name": "private-ac",
        "full_name": "Fredkiss3/private-ac",
        "private": True,
        "owner": {
            "login": "github",
            "id": 1,
            "node_id": "MDEyOk9yZ2FuaXphdGlvbjE=",
            "url": "https://api.github.com/orgs/github",
            "repos_url": "https://api.github.com/orgs/github/repos",
            "events_url": "https://api.github.com/orgs/github/events",
            "avatar_url": "https://github.com/images/error/octocat_happy.gif",
            "gravatar_id": "",
            "html_url": "https://github.com/octocat",
            "followers_url": "https://api.github.com/users/octocat/followers",
            "following_url": "https://api.github.com/users/octocat/following{/other_user}",
            "gists_url": "https://api.github.com/users/octocat/gists{/gist_id}",
            "starred_url": "https://api.github.com/users/octocat/starred{/owner}{/repo}",
            "subscriptions_url": "https://api.github.com/users/octocat/subscriptions",
            "organizations_url": "https://api.github.com/users/octocat/orgs",
            "received_events_url": "https://api.github.com/users/octocat/received_events",
            "type": "User",
            "site_admin": True,
        },
        "html_url": "https://github.com/Fredkiss3/private-ac",
        "description": None,
        "fork": False,
        "url": "https://api.github.com/repos/Fredkiss3/private-ac",
        "forks_url": "https://api.github.com/repos/Fredkiss3/private-ac/forks",
        "keys_url": "https://api.github.com/repos/Fredkiss3/private-ac/keys{/key_id}",
        "collaborators_url": "https://api.github.com/repos/Fredkiss3/private-ac/collaborators{/collaborator}",
        "teams_url": "https://api.github.com/repos/Fredkiss3/private-ac/teams",
        "hooks_url": "https://api.github.com/repos/Fredkiss3/private-ac/hooks",
        "issue_events_url": "https://api.github.com/repos/Fredkiss3/private-ac/issues/events{/number}",
        "events_url": "https://api.github.com/repos/Fredkiss3/private-ac/events",
        "assignees_url": "https://api.github.com/repos/Fredkiss3/private-ac/assignees{/user}",
        "branches_url": "https://api.github.com/repos/Fredkiss3/private-ac/branches{/branch}",
        "tags_url": "https://api.github.com/repos/Fredkiss3/private-ac/tags",
        "blobs_url": "https://api.github.com/repos/Fredkiss3/private-ac/git/blobs{/sha}",
        "git_tags_url": "https://api.github.com/repos/Fredkiss3/private-ac/git/tags{/sha}",
        "git_refs_url": "https://api.github.com/repos/Fredkiss3/private-ac/git/refs{/sha}",
        "trees_url": "https://api.github.com/repos/Fredkiss3/private-ac/git/trees{/sha}",
        "statuses_url": "https://api.github.com/repos/Fredkiss3/private-ac/statuses/{sha}",
        "languages_url": "https://api.github.com/repos/Fredkiss3/private-ac/languages",
        "stargazers_url": "https://api.github.com/repos/Fredkiss3/private-ac/stargazers",
        "contributors_url": "https://api.github.com/repos/Fredkiss3/private-ac/contributors",
        "subscribers_url": "https://api.github.com/repos/Fredkiss3/private-ac/subscribers",
        "subscription_url": "https://api.github.com/repos/Fredkiss3/private-ac/subscription",
        "commits_url": "https://api.github.com/repos/Fredkiss3/private-ac/commits{/sha}",
        "git_commits_url": "https://api.github.com/repos/Fredkiss3/private-ac/git/commits{/sha}",
        "comments_url": "https://api.github.com/repos/Fredkiss3/private-ac/comments{/number}",
        "issue_comment_url": "https://api.github.com/repos/Fredkiss3/private-ac/issues/comments{/number}",
        "contents_url": "https://api.github.com/repos/Fredkiss3/private-ac/contents/{+path}",
        "compare_url": "https://api.github.com/repos/Fredkiss3/private-ac/compare/{base}...{head}",
        "merges_url": "https://api.github.com/repos/Fredkiss3/private-ac/merges",
        "archive_url": "https://api.github.com/repos/Fredkiss3/private-ac/{archive_format}{/ref}",
        "downloads_url": "https://api.github.com/repos/Fredkiss3/private-ac/downloads",
        "issues_url": "https://api.github.com/repos/Fredkiss3/private-ac/issues{/number}",
        "pulls_url": "https://api.github.com/repos/Fredkiss3/private-ac/pulls{/number}",
        "milestones_url": "https://api.github.com/repos/Fredkiss3/private-ac/milestones{/number}",
        "notifications_url": "https://api.github.com/repos/Fredkiss3/private-ac/notifications{?since,all,participating}",
        "labels_url": "https://api.github.com/repos/Fredkiss3/private-ac/labels{/name}",
        "releases_url": "https://api.github.com/repos/Fredkiss3/private-ac/releases{/id}",
        "deployments_url": "https://api.github.com/repos/Fredkiss3/private-ac/deployments",
        "created_at": 1751388518,
        "updated_at": "2025-07-01T16:53:30Z",
        "pushed_at": 1752158454,
        "git_url": "git://github.com/Fredkiss3/private-ac.git",
        "ssh_url": "git@github.com:Fredkiss3/private-ac.git",
        "clone_url": "https://github.com/Fredkiss3/private-ac.git",
        "svn_url": "https://github.com/Fredkiss3/private-ac",
        "homepage": None,
        "size": 11,
        "stargazers_count": 0,
        "watchers_count": 0,
        "language": "TypeScript",
        "has_issues": True,
        "has_projects": True,
        "has_downloads": True,
        "has_wiki": False,
        "has_pages": False,
        "has_discussions": False,
        "forks_count": 0,
        "mirror_url": None,
        "archived": False,
        "disabled": False,
        "open_issues_count": 0,
        "license": None,
        "allow_forking": True,
        "is_template": False,
        "web_commit_signoff_required": False,
        "topics": [],
        "visibility": "private",
        "forks": 0,
        "open_issues": 0,
        "watchers": 0,
        "default_branch": "main",
        "stargazers": 0,
        "master_branch": "main",
    },
    "pusher": {"name": "octocat", "email": "octocat@github.com"},
    "sender": {
        "login": "github",
        "id": 1,
        "node_id": "MDEyOk9yZ2FuaXphdGlvbjE=",
        "url": "https://api.github.com/orgs/github",
        "repos_url": "https://api.github.com/orgs/github/repos",
        "events_url": "https://api.github.com/orgs/github/events",
        "avatar_url": "https://github.com/images/error/octocat_happy.gif",
        "gravatar_id": "",
        "html_url": "https://github.com/octocat",
        "followers_url": "https://api.github.com/users/octocat/followers",
        "following_url": "https://api.github.com/users/octocat/following{/other_user}",
        "gists_url": "https://api.github.com/users/octocat/gists{/gist_id}",
        "starred_url": "https://api.github.com/users/octocat/starred{/owner}{/repo}",
        "subscriptions_url": "https://api.github.com/users/octocat/subscriptions",
        "organizations_url": "https://api.github.com/users/octocat/orgs",
        "received_events_url": "https://api.github.com/users/octocat/received_events",
        "type": "User",
        "site_admin": True,
    },
    "installation": {
        "id": 1,
    },
    "created": False,
    "deleted": False,
    "forced": False,
    "base_ref": None,
    "compare": "https://github.com/Fredkiss3/private-ac/compare/e0522b4784bd...1c4801f2367a",
    "commits": [
        {
            "id": "1c4801f2367acc933760f68e3e611cb2fd1b630d",
            "tree_id": "290164d081ce3e4589c0acb455ed1056cf6a9ab4",
            "distinct": True,
            "message": "simple change",
            "timestamp": "2025-07-10T16:40:50+02:00",
            "url": "https://github.com/Fredkiss3/private-ac/commit/1c4801f2367acc933760f68e3e611cb2fd1b630d",
            "author": {
                "name": "octocat",
                "email": "octocat@github.com",
                "username": "Octocat",
            },
            "committer": {
                "name": "octocat",
                "email": "octocat@github.com",
                "username": "Octocat",
            },
            "added": [],
            "removed": [],
            "modified": ["routes/index.tsx"],
        }
    ],
    "head_commit": {
        "id": "1c4801f2367acc933760f68e3e611cb2fd1b630d",
        "tree_id": "290164d081ce3e4589c0acb455ed1056cf6a9ab4",
        "distinct": True,
        "message": "simple change",
        "timestamp": "2025-07-10T16:40:50+02:00",
        "url": "https://github.com/Fredkiss3/private-ac/commit/1c4801f2367acc933760f68e3e611cb2fd1b630d",
        "author": {
            "name": "octocat",
            "email": "octocat@github.com",
            "username": "Octocat",
        },
        "committer": {
            "name": "octocat",
            "email": "octocat@github.com",
            "username": "Octocat",
        },
        "added": [],
        "removed": [],
        "modified": ["routes/index.tsx"],
    },
}


class DeployGithubServiceFromWebhookPushViewTests(AuthAPITestCase):
    @responses.activate
    async def test_deploy_service_from_push_webhook_deploy_service_succesfully(self):
        await self.aLoginUser()
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)
        github_api_pattern = re.compile(
            r"^https://api\.github\.com/app/installations/.*",
            re.IGNORECASE,
        )
        responses.add(
            responses.POST,
            url=github_api_pattern,
            status=status.HTTP_200_OK,
            json={"token": generate_random_chars(32)},
        )

        gh_app = await GitHubApp.objects.acreate(
            webhook_secret=MANIFEST_DATA["webhook_secret"],
            app_id=MANIFEST_DATA["id"],
            name=MANIFEST_DATA["name"],
            client_id=MANIFEST_DATA["client_id"],
            client_secret=MANIFEST_DATA["client_secret"],
            private_key=MANIFEST_DATA["pem"],
            app_url=MANIFEST_DATA["html_url"],
            installation_id=1,
        )
        git_app = await GitApp.objects.acreate(github=gh_app)
        # install app
        response = await self.async_client.post(
            reverse("git_connectors:github.webhook"),
            data=INSTALLATION_CREATED_WEBHOOK_DATA,
            headers=get_signed_event_headers(
                GithubWebhookEvent.INSTALLATION,
                INSTALLATION_CREATED_WEBHOOK_DATA,
                gh_app.webhook_secret,
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        p, service = await self.acreate_git_service(
            repository_url="https://github.com/Fredkiss3/private-ac",
            git_app_id=git_app.id,
        )
        response = await self.async_client.post(
            reverse("git_connectors:github.webhook"),
            data=GITHUB_PUSH_WEBHOOK_EVENT_DATA,
            headers=get_signed_event_headers(
                GithubWebhookEvent.PUSH,
                GITHUB_PUSH_WEBHOOK_EVENT_DATA,
                gh_app.webhook_secret,
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        new_deployment = cast(Deployment, await service.alatest_production_deployment)
        self.assertIsNotNone(new_deployment)
        swarm_service = self.fake_docker_client.get_deployment_service(new_deployment)
        self.assertIsNotNone(swarm_service)
        self.assertEqual(Deployment.DeploymentStatus.HEALTHY, new_deployment.status)
        self.assertTrue(new_deployment.is_current_production)
        self.assertEqual(
            Deployment.DeploymentTriggerMethod.AUTO, new_deployment.trigger_method
        )

        self.assertEqual(
            GITHUB_PUSH_WEBHOOK_EVENT_DATA["head_commit"]["message"],
            new_deployment.commit_message,
        )
        self.assertEqual(
            GITHUB_PUSH_WEBHOOK_EVENT_DATA["head_commit"]["id"],
            new_deployment.commit_sha,
        )
        self.assertEqual(
            GITHUB_PUSH_WEBHOOK_EVENT_DATA["head_commit"]["author"]["name"],
            new_deployment.commit_author_name,
        )

    @responses.activate
    async def test_push_to_a_different_branch_do_not_deploy_the_service(self):
        await self.aLoginUser()
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)
        github_api_pattern = re.compile(
            r"^https://api\.github\.com/app/installations/.*",
            re.IGNORECASE,
        )
        responses.add(
            responses.POST,
            url=github_api_pattern,
            status=status.HTTP_200_OK,
            json={"token": generate_random_chars(32)},
        )

        gh_app = await GitHubApp.objects.acreate(
            webhook_secret=MANIFEST_DATA["webhook_secret"],
            app_id=MANIFEST_DATA["id"],
            name=MANIFEST_DATA["name"],
            client_id=MANIFEST_DATA["client_id"],
            client_secret=MANIFEST_DATA["client_secret"],
            private_key=MANIFEST_DATA["pem"],
            app_url=MANIFEST_DATA["html_url"],
            installation_id=1,
        )
        git_app = await GitApp.objects.acreate(github=gh_app)
        # install app
        response = await self.async_client.post(
            reverse("git_connectors:github.webhook"),
            data=INSTALLATION_CREATED_WEBHOOK_DATA,
            headers=get_signed_event_headers(
                GithubWebhookEvent.INSTALLATION,
                INSTALLATION_CREATED_WEBHOOK_DATA,
                gh_app.webhook_secret,
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        p, service = await self.acreate_git_service(
            repository_url="https://github.com/Fredkiss3/private-ac",
            git_app_id=git_app.id,
        )

        data = dict(**GITHUB_PUSH_WEBHOOK_EVENT_DATA)
        data["ref"] = "refs/heads/testing"
        response = await self.async_client.post(
            reverse("git_connectors:github.webhook"),
            data=data,
            headers=get_signed_event_headers(
                GithubWebhookEvent.PUSH,
                data,
                gh_app.webhook_secret,
            ),
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        self.assertEqual(0, await service.deployments.acount())

    @responses.activate
    async def test_push_to_a_non_branch_do_not_deploy_the_service(self):
        await self.aLoginUser()
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)
        github_api_pattern = re.compile(
            r"^https://api\.github\.com/app/installations/.*",
            re.IGNORECASE,
        )
        responses.add(
            responses.POST,
            url=github_api_pattern,
            status=status.HTTP_200_OK,
            json={"token": generate_random_chars(32)},
        )

        gh_app = await GitHubApp.objects.acreate(
            webhook_secret=MANIFEST_DATA["webhook_secret"],
            app_id=MANIFEST_DATA["id"],
            name=MANIFEST_DATA["name"],
            client_id=MANIFEST_DATA["client_id"],
            client_secret=MANIFEST_DATA["client_secret"],
            private_key=MANIFEST_DATA["pem"],
            app_url=MANIFEST_DATA["html_url"],
            installation_id=1,
        )
        git_app = await GitApp.objects.acreate(github=gh_app)
        # install app
        response = await self.async_client.post(
            reverse("git_connectors:github.webhook"),
            data=INSTALLATION_CREATED_WEBHOOK_DATA,
            headers=get_signed_event_headers(
                GithubWebhookEvent.INSTALLATION,
                INSTALLATION_CREATED_WEBHOOK_DATA,
                gh_app.webhook_secret,
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        p, service = await self.acreate_git_service(
            repository_url="https://github.com/Fredkiss3/private-ac",
            git_app_id=git_app.id,
        )

        data = dict(**GITHUB_PUSH_WEBHOOK_EVENT_DATA)
        data["ref"] = "refs/tags/main"
        response = await self.async_client.post(
            reverse("git_connectors:github.webhook"),
            data=data,
            headers=get_signed_event_headers(
                GithubWebhookEvent.PUSH,
                data,
                gh_app.webhook_secret,
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        self.assertEqual(0, await service.deployments.acount())

    @responses.activate
    async def test_github_pushes_ignore_unwatched_paths(self):
        await self.aLoginUser()
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)
        github_api_pattern = re.compile(
            r"^https://api\.github\.com/app/installations/.*",
            re.IGNORECASE,
        )
        responses.add(
            responses.POST,
            url=github_api_pattern,
            status=status.HTTP_200_OK,
            json={"token": generate_random_chars(32)},
        )

        gh_app = await GitHubApp.objects.acreate(
            webhook_secret=MANIFEST_DATA["webhook_secret"],
            app_id=MANIFEST_DATA["id"],
            name=MANIFEST_DATA["name"],
            client_id=MANIFEST_DATA["client_id"],
            client_secret=MANIFEST_DATA["client_secret"],
            private_key=MANIFEST_DATA["pem"],
            app_url=MANIFEST_DATA["html_url"],
            installation_id=1,
        )
        git_app = await GitApp.objects.acreate(github=gh_app)
        # install app
        response = await self.async_client.post(
            reverse("git_connectors:github.webhook"),
            data=INSTALLATION_CREATED_WEBHOOK_DATA,
            headers=get_signed_event_headers(
                GithubWebhookEvent.INSTALLATION,
                INSTALLATION_CREATED_WEBHOOK_DATA,
                gh_app.webhook_secret,
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        p, service = await self.acreate_git_service(
            repository_url="https://github.com/Fredkiss3/private-ac",
            git_app_id=git_app.id,
        )
        service.watch_paths = "routes/api/*"
        await service.asave()

        response = await self.async_client.post(
            reverse("git_connectors:github.webhook"),
            data=GITHUB_PUSH_WEBHOOK_EVENT_DATA,
            headers=get_signed_event_headers(
                GithubWebhookEvent.PUSH,
                GITHUB_PUSH_WEBHOOK_EVENT_DATA,
                gh_app.webhook_secret,
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(0, await service.deployments.acount())

    @responses.activate
    async def test_deploy_service_from_github_push_with_empty_head_commit_resolves_commit_from_HEAD(
        self,
    ):
        await self.aLoginUser()
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)
        github_api_pattern = re.compile(
            r"^https://api\.github\.com/app/installations/.*",
            re.IGNORECASE,
        )
        responses.add(
            responses.POST,
            url=github_api_pattern,
            status=status.HTTP_200_OK,
            json={"token": generate_random_chars(32)},
        )

        gh_app = await GitHubApp.objects.acreate(
            webhook_secret=MANIFEST_DATA["webhook_secret"],
            app_id=MANIFEST_DATA["id"],
            name=MANIFEST_DATA["name"],
            client_id=MANIFEST_DATA["client_id"],
            client_secret=MANIFEST_DATA["client_secret"],
            private_key=MANIFEST_DATA["pem"],
            app_url=MANIFEST_DATA["html_url"],
            installation_id=1,
        )
        git_app = await GitApp.objects.acreate(github=gh_app)
        # install app
        response = await self.async_client.post(
            reverse("git_connectors:github.webhook"),
            data=INSTALLATION_CREATED_WEBHOOK_DATA,
            headers=get_signed_event_headers(
                GithubWebhookEvent.INSTALLATION,
                INSTALLATION_CREATED_WEBHOOK_DATA,
                gh_app.webhook_secret,
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        self.assertEqual(status.HTTP_200_OK, response.status_code)
        p, service = await self.acreate_git_service(
            repository_url="https://github.com/Fredkiss3/private-ac",
            git_app_id=git_app.id,
        )

        data = dict(**GITHUB_PUSH_WEBHOOK_EVENT_DATA)
        data["head_commit"] = None
        response = await self.async_client.post(
            reverse("git_connectors:github.webhook"),
            data=data,
            headers=get_signed_event_headers(
                GithubWebhookEvent.PUSH,
                data,
                gh_app.webhook_secret,
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        new_deployment = cast(Deployment, await service.alatest_production_deployment)
        self.assertIsNotNone(new_deployment)
        swarm_service = self.fake_docker_client.get_deployment_service(new_deployment)
        self.assertIsNotNone(swarm_service)
        self.assertEqual(Deployment.DeploymentStatus.HEALTHY, new_deployment.status)
        self.assertTrue(new_deployment.is_current_production)
        self.assertEqual(
            Deployment.DeploymentTriggerMethod.AUTO, new_deployment.trigger_method
        )

        self.assertEqual(
            self.fake_git.DEFAULT_COMMIT_SHA,
            new_deployment.commit_sha,
        )
        self.assertEqual(
            self.fake_git.DEFAULT_COMMIT_MESSAGE,
            new_deployment.commit_message,
        )
        self.assertEqual(
            self.fake_git.DEFAULT_COMMIT_AUTHOR_NAME,
            new_deployment.commit_author_name,
        )
