import hashlib
import hmac
import json
from typing import cast
from .base import AuthAPITestCase
from django.urls import reverse
from rest_framework import status

from ..models import (
    Project,
    Deployment,
    Service,
    # ArchivedDockerService,
    Environment,
    DeploymentChange,
    # Volume,
    # URL,
    GitApp,
    PreviewTemplate,
)

from django.conf import settings

# from temporal.activities import get_env_network_resource_name
from ..utils import jprint, generate_random_chars, find_item_in_sequence
import responses
import re

from git_connectors.models import GitHubApp
from git_connectors.views import GithubWebhookEvent
from asgiref.sync import sync_to_async
from django.utils.text import slugify


def get_signed_event_headers(event: str, payload_body: dict, secret: str):
    hash_object = hmac.new(
        secret.encode("utf-8"),
        msg=json.dumps(payload_body).encode("utf-8"),
        digestmod=hashlib.sha256,
    )
    return {
        "X-GitHub-Event": event,
        "X-Hub-Signature-256": "sha256=" + hash_object.hexdigest(),
    }


GITHUB_MANIFEST_DATA = {
    "id": 1,
    "slug": "octoapp",
    "node_id": "MDxOkludGVncmF0aW9uMQ==",
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
    "name": "Octocat App",
    "description": "",
    "external_url": "https://example.com",
    "html_url": "https://github.com/apps/octoapp",
    "created_at": "2017-07-08T16:18:44-04:00",
    "updated_at": "2017-07-08T16:18:44-04:00",
    "permissions": {
        "metadata": "read",
        "contents": "read",
        "issues": "write",
        "single_file": "write",
    },
    "events": ["push", "pull_request"],
    "client_id": "Iv1.8a61f9b3a7aba766",
    "client_secret": "1726be1638095a19edd134c77bde3aa2ece1e5d8",
    "webhook_secret": "e340154128314309424b7c8e90325147d99fdafa",
    "pem": "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEAuEPzOUE+kiEH1WLiMeBytTEF856j0hOVcSUSUkZxKvqczkWM\n9vo1gDyC7ZXhdH9fKh32aapba3RSsp4ke+giSmYTk2mGR538ShSDxh0OgpJmjiKP\nX0Bj4j5sFqfXuCtl9SkH4iueivv4R53ktqM+n6hk98l6hRwC39GVIblAh2lEM4L/\n6WvYwuQXPMM5OG2Ryh2tDZ1WS5RKfgq+9ksNJ5Q9UtqtqHkO+E63N5OK9sbzpUUm\noNaOl3udTlZD3A8iqwMPVxH4SxgATBPAc+bmjk6BMJ0qIzDcVGTrqrzUiywCTLma\nszdk8GjzXtPDmuBgNn+o6s02qVGpyydgEuqmTQIDAQABAoIBACL6AvkjQVVLn8kJ\ndBYznJJ4M8ECo+YEgaFwgAHODT0zRQCCgzd+Vxl4YwHmKV2Lr+y2s0drZt8GvYva\nKOK8NYYZyi15IlwFyRXmvvykF1UBpSXluYFDH7KaVroWMgRreHcIys5LqVSIb6Bo\ngDmK0yBLPp8qR29s2b7ScZRtLaqGJiX+j55rNzrZwxHkxFHyG9OG+u9IsBElcKCP\nkYCVE8ZdYexfnKOZbgn2kZB9qu0T/Mdvki8yk3I2bI6xYO24oQmhnT36qnqWoCBX\nNuCNsBQgpYZeZET8mEAUmo9d+ABmIHIvSs005agK8xRaP4+6jYgy6WwoejJRF5yd\nNBuF7aECgYEA50nZ4FiZYV0vcJDxFYeY3kYOvVuKn8OyW+2rg7JIQTremIjv8FkE\nZnwuF9ZRxgqLxUIfKKfzp/5l5LrycNoj2YKfHKnRejxRWXqG+ZETfxxlmlRns0QG\nJ4+BYL0CoanDSeA4fuyn4Bv7cy/03TDhfg/Uq0Aeg+hhcPE/vx3ebPsCgYEAy/Pv\neDLssOSdeyIxf0Brtocg6aPXIVaLdus+bXmLg77rJIFytAZmTTW8SkkSczWtucI3\nFI1I6sei/8FdPzAl62/JDdlf7Wd9K7JIotY4TzT7Tm7QU7xpfLLYIP1bOFjN81rk\n77oOD4LsXcosB/U6s1blPJMZ6AlO2EKs10UuR1cCgYBipzuJ2ADEaOz9RLWwi0AH\nPza2Sj+c2epQD9ZivD7Zo/Sid3ZwvGeGF13JyR7kLEdmAkgsHUdu1rI7mAolXMaB\n1pdrsHureeLxGbRM6za3tzMXWv1Il7FQWoPC8ZwXvMOR1VQDv4nzq7vbbA8z8c+c\n57+8tALQHOTDOgQIzwK61QKBgERGVc0EJy4Uag+VY8J4m1ZQKBluqo7TfP6DQ7O8\nM5MX73maB/7yAX8pVO39RjrhJlYACRZNMbK+v/ckEQYdJSSKmGCVe0JrGYDuPtic\nI9+IGfSorf7KHPoMmMN6bPYQ7Gjh7a++tgRFTMEc8956Hnt4xGahy9NcglNtBpVN\n6G8jAoGBAMCh028pdzJa/xeBHLLaVB2sc0Fe7993WlsPmnVE779dAz7qMscOtXJK\nfgtriltLSSD6rTA9hUAsL/X62rY0wdXuNdijjBb/qvrx7CAV6i37NK1CjABNjsfG\nZM372Ac6zc1EqSrid2IjET1YqyIW2KGLI1R2xbQc98UGlt48OdWu\n-----END RSA PRIVATE KEY-----\n",
}

GITHUB_INSTALLATION_CREATED_WEBHOOK_DATA = {
    "action": "created",
    "installation": {
        "id": 1,
        "client_id": "Iv23li1kL280HIpnXEuO",
        "account": {
            "login": "octocat",
            "id": 100,
            "node_id": "MDxOkludGVncmF0aW9uMQ==",
            "html_url": "https://github.com/octocat",
            "type": "User",
            "user_view_type": "public",
            "site_admin": False,
        },
        "repository_selection": "all",
        "repositories_url": "https://api.github.com/installation/repositories",
        "html_url": "https://github.com/settings/installations/1",
        "app_id": 1,
        "app_slug": "zaneops-fredkiss3-app",
        "target_id": 100,
        "target_type": "User",
        "permissions": {
            "contents": "read",
            "metadata": "read",
            "pull_requests": "write",
        },
        "events": ["pull_request", "push"],
        "created_at": "2025-07-03T13:26:01.000+02:00",
        "updated_at": "2025-07-03T13:26:01.000+02:00",
        "single_file_name": None,
        "has_multiple_single_files": False,
        "single_file_paths": [],
        "suspended_by": None,
        "suspended_at": None,
    },
    "repositories": [
        {
            "id": 1,
            "node_id": "MDEwOlJlcG9zaXRvcnkxNDIyNjAyNTk=",
            "name": "Projet-dietetique",
            "full_name": "Fredkiss3/Projet-dietetique",
            "private": False,
        },
        {
            "id": 2,
            "node_id": "MDEwOlJlcG9zaXRvcnkyMDM0MjYwOTk=",
            "name": "reserve_stage",
            "full_name": "Fredkiss3/reserve_stage",
            "private": True,
        },
        {
            "id": 3,
            "node_id": "MDEwOlJlcG9zaXRvcnkyMzg4NjkzNTY=",
            "name": "kge",
            "full_name": "Fredkiss3/kge",
            "private": False,
        },
        {
            "id": 4,
            "node_id": "R_kgDOPFHpfg",
            "name": "private-ac",
            "full_name": "Fredkiss3/private-ac",
            "private": True,
        },
    ],
    "requester": None,
    "sender": {
        "login": "octocat",
        "id": 100,
        "node_id": "MDxOkludGVncmF0aW9uMQ==",
        "html_url": "https://github.com/octocat",
        "type": "User",
        "user_view_type": "public",
        "site_admin": False,
    },
}


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


class MoreEnvironmentViewTests(AuthAPITestCase):
    async def test_deployed_services_are_added_with_global_alias_using_env_id_as_suffix(
        self,
    ):
        p, service = await self.acreate_and_deploy_redis_docker_service()

        deployment = cast(Deployment, await service.deployments.afirst())
        fake_service = self.fake_docker_client.get_deployment_service(deployment)
        global_network_config = find_item_in_sequence(lambda net: net["Target"] == "zane", fake_service.networks)  # type: ignore

        global_aliases = [
            alias
            for alias in global_network_config["Aliases"]  # type: ignore
            if "blue" not in alias and "green" not in alias
        ]
        self.assertEqual(2, len(global_aliases))


class PreviewEnvironmentsViewTests(AuthAPITestCase):
    def create_and_install_github_app(self):
        self.loginUser()
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

        github = GitHubApp.objects.create(
            webhook_secret=GITHUB_MANIFEST_DATA["webhook_secret"],
            app_id=GITHUB_MANIFEST_DATA["id"],
            name=GITHUB_MANIFEST_DATA["name"],
            client_id=GITHUB_MANIFEST_DATA["client_id"],
            client_secret=GITHUB_MANIFEST_DATA["client_secret"],
            private_key=GITHUB_MANIFEST_DATA["pem"],
            app_url=GITHUB_MANIFEST_DATA["html_url"],
            installation_id=1,
        )
        gitapp = GitApp.objects.create(github=github)

        # install app
        response = self.client.post(
            reverse("git_connectors:github.webhook"),
            data=GITHUB_INSTALLATION_CREATED_WEBHOOK_DATA,
            headers=get_signed_event_headers(
                GithubWebhookEvent.INSTALLATION,
                GITHUB_INSTALLATION_CREATED_WEBHOOK_DATA,
                github.webhook_secret,
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        return gitapp

    async def acreate_and_install_github_app(self):
        return await sync_to_async(self.create_and_install_github_app)()

    def test_create_default_preview_template_when_creating_a_project(self):
        self.loginUser()
        p, _ = self.create_redis_docker_service()
        default_template = cast(
            PreviewTemplate, p.preview_templates.filter(is_default=True).first()
        )
        self.assertIsNotNone(default_template)
        self.assertEqual(p.production_env, default_template.base_environment)
        self.assertEqual(
            PreviewTemplate.PreviewCloneStrategy.ALL,
            default_template.clone_strategy,
        )
        self.assertEqual(0, default_template.services_to_clone.count())

    def test_prevent_creating_environment_with_preview_prefix(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        project = Project.objects.get(slug="zane-ops")
        response = self.client.post(
            reverse(
                "zane_api:projects.environment.create", kwargs={"slug": project.slug}
            ),
            data={"name": "preview-staging"},
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        staging_env = project.environments.filter(name="preview-staging").first()
        self.assertIsNone(staging_env)

    def test_prevent_cloning_environment_with_preview_prefix(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        project = Project.objects.get(slug="zane-ops")
        response = self.client.post(
            reverse(
                "zane_api:projects.environment.clone",
                kwargs={"slug": project.slug, "env_slug": Environment.PRODUCTION_ENV},
            ),
            data={"name": "preview-staging"},
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        staging_env = project.environments.filter(name="preview-staging").first()
        self.assertIsNone(staging_env)

    @responses.activate
    def test_trigger_preview_environment_via_deploy_token_create_preview_env(self):
        gitapp = self.create_and_install_github_app()

        self.create_and_deploy_redis_docker_service()
        p, service = self.create_and_deploy_git_service(
            slug="deno-fresh",
            repository="https://github.com/Fredkiss3/private-ac",
            git_app_id=gitapp.id,
        )
        response = self.client.post(
            reverse(
                "zane_api:services.git.trigger_preview_env",
                kwargs={"deploy_token": service.deploy_token},
            ),
            data={"branch_name": "feat/test-1"},
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        jprint(response.json())

        preview_env = cast(
            Environment,
            p.environments.filter(is_preview=True).first(),
        )
        self.assertIsNotNone(preview_env)
        self.assertTrue(
            preview_env.name.startswith(f"preview-{slugify('feat/test-1')}")
        )
        self.assertEqual("feat/test-1", preview_env.preview_branch)
        self.assertEqual(service, preview_env.preview_service)
        self.assertEqual("HEAD", preview_env.preview_commit_sha)
        self.assertEqual(
            Environment.PreviewSourceTrigger.API, preview_env.preview_source_trigger
        )
        self.assertTrue(preview_env.preview_deploy_approved)
        self.assertEqual(
            p.preview_templates.get(is_default=True), preview_env.preview_template
        )

    @responses.activate
    def test_trigger_preview_environment_via_deploy_token_clone_services(self):
        gitapp = self.create_and_install_github_app()

        _, redis_service = self.create_and_deploy_redis_docker_service()
        p, git_service = self.create_and_deploy_git_service(
            slug="deno-fresh",
            repository="https://github.com/Fredkiss3/private-ac",
            git_app_id=gitapp.id,
        )
        response = self.client.post(
            reverse(
                "zane_api:services.git.trigger_preview_env",
                kwargs={"deploy_token": git_service.deploy_token},
            ),
            data={"branch_name": "feat/test-1"},
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        jprint(response.json())

        preview_env = cast(
            Environment,
            p.environments.filter(is_preview=True).first(),
        )
        self.assertIsNotNone(preview_env)
        self.assertTrue(
            preview_env.name.startswith(f"preview-{slugify('feat/test-1')}")
        )
        self.assertEqual(2, preview_env.services.count())

        # The state changes are applied and deployments are created
        self.assertEqual(
            2,
            Deployment.objects.filter(
                service__environment__name=preview_env.name
            ).count(),
        )

        self.assertEqual(
            0,
            DeploymentChange.objects.filter(
                service__environment__name=preview_env.name, applied=False
            ).count(),
        )

        cloned_git_service = preview_env.services.get(slug=git_service.slug)
        cloned_redis_service = preview_env.services.get(slug=redis_service.slug)
        self.assertEqual(
            redis_service.network_alias, cloned_redis_service.network_alias
        )
        self.assertNotEqual(
            redis_service.global_network_alias,
            cloned_redis_service.global_network_alias,
        )
        self.assertNotEqual(
            redis_service.deploy_token, cloned_redis_service.deploy_token
        )
        self.assertEqual("feat/test-1", cloned_git_service.branch_name)

    @responses.activate
    async def test_trigger_preview_environment_via_deploy_token_deploy_services(self):
        gitapp = await self.acreate_and_install_github_app()
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)

        await self.acreate_and_deploy_redis_docker_service()
        p, service = await self.acreate_and_deploy_git_service(
            slug="deno-fresh",
            repository="https://github.com/Fredkiss3/private-ac",
            git_app_id=gitapp.id,
        )
        response = await self.async_client.post(
            reverse(
                "zane_api:services.git.trigger_preview_env",
                kwargs={"deploy_token": service.deploy_token},
            ),
            data={"branch_name": "test-1"},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        preview_env = cast(
            Environment, await p.environments.filter(is_preview=True).afirst()
        )
        self.assertIsNotNone(preview_env)

        services_in_preview = Service.objects.filter(environment=preview_env)
        self.assertEqual(2, await services_in_preview.acount())

        self.assertEqual(
            2,
            await Deployment.objects.filter(
                service__environment__name=preview_env.name
            ).acount(),
        )

        self.assertEqual(
            0,
            await DeploymentChange.objects.filter(
                service__environment__name=preview_env.name, applied=False
            ).acount(),
        )
        git_service = await services_in_preview.filter(
            type=Service.ServiceType.GIT_REPOSITORY
        ).afirst()
        docker_service = await services_in_preview.filter(
            type=Service.ServiceType.DOCKER_REGISTRY
        ).afirst()

        swarm_service = self.fake_docker_client.get_deployment_service(
            await git_service.deployments.afirst()  # type: ignore
        )
        self.assertIsNotNone(swarm_service)
        swarm_service = self.fake_docker_client.get_deployment_service(
            await docker_service.deployments.afirst()  # type: ignore
        )
        self.assertIsNotNone(swarm_service)

        service_images = self.fake_docker_client.images_list(
            filters={"label": [f"parent={git_service.id}"]}  # type: ignore
        )
        self.assertEqual(1, len(service_images))

    @responses.activate
    async def test_preview_environment_is_closed_when_branch_is_deleted(self):
        gitapp = await self.acreate_and_install_github_app()
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)

        await self.acreate_and_deploy_redis_docker_service()
        p, service = await self.acreate_and_deploy_git_service(
            slug="deno-fresh",
            repository="https://github.com/Fredkiss3/private-ac",
            git_app_id=gitapp.id,
        )
        response = await self.async_client.post(
            reverse(
                "zane_api:services.git.trigger_preview_env",
                kwargs={"deploy_token": service.deploy_token},
            ),
            data={"branch_name": "feat/test-preview"},
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        preview_env = cast(
            Environment, await p.environments.filter(is_preview=True).afirst()
        )
        self.assertIsNotNone(preview_env)

        push_data = dict(**GITHUB_PUSH_WEBHOOK_EVENT_DATA)
        # delete branch `test-preview`
        push_data["ref"] = "refs/heads/feat/test-preview"
        push_data["deleted"] = True
        github = cast(GitHubApp, gitapp.github)
        response = await self.async_client.post(
            reverse("git_connectors:github.webhook"),
            data=push_data,
            headers=get_signed_event_headers(
                GithubWebhookEvent.PUSH,
                push_data,
                github.webhook_secret,
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        self.assertEqual(0, await p.environments.filter(is_preview=True).acount())
        self.assertEqual(2, await p.services.acount())
        network = self.fake_docker_client.get_env_network(preview_env)
        self.assertIsNone(network)

    @responses.activate
    async def test_preview_environment_is_locked_when_push_is_made_to_branch_with_non_head_commit(
        self,
    ):
        self.assertTrue(False)

    def test_create_preview_environment_merge_shared_environment_variables_from_template(
        self,
    ):
        self.assertTrue(False)

    def test_create_preview_environment_with_other_template_only_clone_specified_services(
        self,
    ):
        self.assertTrue(False)

    def test_prevent_renaming_preview_envs(self):
        self.assertTrue(False)

    @responses.activate
    async def test_create_preview_with_invalid_template_errors(self):
        gitapp = await self.acreate_and_install_github_app()
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)

        await self.acreate_and_deploy_redis_docker_service()
        p, service = await self.acreate_and_deploy_git_service(
            slug="deno-fresh",
            repository="https://github.com/Fredkiss3/private-ac",
            git_app_id=gitapp.id,
        )
        response = await self.async_client.post(
            reverse(
                "zane_api:services.git.trigger_preview_env",
                kwargs={"deploy_token": service.deploy_token},
            ),
            data={"branch_name": "test-1", "template": "invalid"},
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    @responses.activate
    async def test_create_preview_with_invalid_branch_errors(self):
        gitapp = await self.acreate_and_install_github_app()
        responses.add_passthru(settings.CADDY_PROXY_ADMIN_HOST)
        responses.add_passthru(settings.LOKI_HOST)

        await self.acreate_and_deploy_redis_docker_service()
        p, service = await self.acreate_and_deploy_git_service(
            slug="deno-fresh",
            repository="https://github.com/Fredkiss3/private-ac",
            git_app_id=gitapp.id,
        )
        response = await self.async_client.post(
            reverse(
                "zane_api:services.git.trigger_preview_env",
                kwargs={"deploy_token": service.deploy_token},
            ),
            data={
                "branch_name": self.fake_git.NON_EXISTENT_BRANCH,
            },
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
