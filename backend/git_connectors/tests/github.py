import json
import re
from django.urls import reverse
from rest_framework import status
from urllib.parse import urlencode

from zane_api.tests.base import AuthAPITestCase
from zane_api.utils import generate_random_chars, jprint
import responses
from zane_api.models import GitApp
from ..models import GithubApp
from ..serializers import GithubWebhookEvent
import hashlib
import hmac

# Create your tests here.

MANIFEST_DATA = {
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


REPOSITORY_LIST = {
    "total_count": 1,
    "repositories": [
        {
            "id": 1296269,
            "node_id": "MDEwOlJlcG9zaXRvcnkxMjk2MjY5",
            "name": "Hello-World",
            "full_name": "octocat/Hello-World",
            "owner": {
                "login": "octocat",
                "id": 1,
                "node_id": "MDQ6VXNlcjE=",
                "avatar_url": "https://github.com/images/error/octocat_happy.gif",
                "gravatar_id": "",
                "url": "https://api.github.com/users/octocat",
                "html_url": "https://github.com/octocat",
                "followers_url": "https://api.github.com/users/octocat/followers",
                "following_url": "https://api.github.com/users/octocat/following{/other_user}",
                "gists_url": "https://api.github.com/users/octocat/gists{/gist_id}",
                "starred_url": "https://api.github.com/users/octocat/starred{/owner}{/repo}",
                "subscriptions_url": "https://api.github.com/users/octocat/subscriptions",
                "organizations_url": "https://api.github.com/users/octocat/orgs",
                "repos_url": "https://api.github.com/users/octocat/repos",
                "events_url": "https://api.github.com/users/octocat/events{/privacy}",
                "received_events_url": "https://api.github.com/users/octocat/received_events",
                "type": "User",
                "site_admin": False,
            },
            "private": True,
            "html_url": "https://github.com/octocat/Hello-World",
            "description": "This your first repo!",
            "fork": False,
            "url": "https://api.github.com/repos/octocat/Hello-World",
            "archive_url": "https://api.github.com/repos/octocat/Hello-World/{archive_format}{/ref}",
            "assignees_url": "https://api.github.com/repos/octocat/Hello-World/assignees{/user}",
            "blobs_url": "https://api.github.com/repos/octocat/Hello-World/git/blobs{/sha}",
            "branches_url": "https://api.github.com/repos/octocat/Hello-World/branches{/branch}",
            "collaborators_url": "https://api.github.com/repos/octocat/Hello-World/collaborators{/collaborator}",
            "comments_url": "https://api.github.com/repos/octocat/Hello-World/comments{/number}",
            "commits_url": "https://api.github.com/repos/octocat/Hello-World/commits{/sha}",
            "compare_url": "https://api.github.com/repos/octocat/Hello-World/compare/{base}...{head}",
            "contents_url": "https://api.github.com/repos/octocat/Hello-World/contents/{+path}",
            "contributors_url": "https://api.github.com/repos/octocat/Hello-World/contributors",
            "deployments_url": "https://api.github.com/repos/octocat/Hello-World/deployments",
            "downloads_url": "https://api.github.com/repos/octocat/Hello-World/downloads",
            "events_url": "https://api.github.com/repos/octocat/Hello-World/events",
            "forks_url": "https://api.github.com/repos/octocat/Hello-World/forks",
            "git_commits_url": "https://api.github.com/repos/octocat/Hello-World/git/commits{/sha}",
            "git_refs_url": "https://api.github.com/repos/octocat/Hello-World/git/refs{/sha}",
            "git_tags_url": "https://api.github.com/repos/octocat/Hello-World/git/tags{/sha}",
            "git_url": "git:github.com/octocat/Hello-World.git",
            "issue_comment_url": "https://api.github.com/repos/octocat/Hello-World/issues/comments{/number}",
            "issue_events_url": "https://api.github.com/repos/octocat/Hello-World/issues/events{/number}",
            "issues_url": "https://api.github.com/repos/octocat/Hello-World/issues{/number}",
            "keys_url": "https://api.github.com/repos/octocat/Hello-World/keys{/key_id}",
            "labels_url": "https://api.github.com/repos/octocat/Hello-World/labels{/name}",
            "languages_url": "https://api.github.com/repos/octocat/Hello-World/languages",
            "merges_url": "https://api.github.com/repos/octocat/Hello-World/merges",
            "milestones_url": "https://api.github.com/repos/octocat/Hello-World/milestones{/number}",
            "notifications_url": "https://api.github.com/repos/octocat/Hello-World/notifications{?since,all,participating}",
            "pulls_url": "https://api.github.com/repos/octocat/Hello-World/pulls{/number}",
            "releases_url": "https://api.github.com/repos/octocat/Hello-World/releases{/id}",
            "ssh_url": "git@github.com:octocat/Hello-World.git",
            "stargazers_url": "https://api.github.com/repos/octocat/Hello-World/stargazers",
            "statuses_url": "https://api.github.com/repos/octocat/Hello-World/statuses/{sha}",
            "subscribers_url": "https://api.github.com/repos/octocat/Hello-World/subscribers",
            "subscription_url": "https://api.github.com/repos/octocat/Hello-World/subscription",
            "tags_url": "https://api.github.com/repos/octocat/Hello-World/tags",
            "teams_url": "https://api.github.com/repos/octocat/Hello-World/teams",
            "trees_url": "https://api.github.com/repos/octocat/Hello-World/git/trees{/sha}",
            "clone_url": "https://github.com/octocat/Hello-World.git",
            "mirror_url": "git:git.example.com/octocat/Hello-World",
            "hooks_url": "https://api.github.com/repos/octocat/Hello-World/hooks",
            "svn_url": "https://svn.github.com/octocat/Hello-World",
            "homepage": "https://github.com",
            "language": None,
            "forks_count": 9,
            "stargazers_count": 80,
            "watchers_count": 80,
            "size": 108,
            "default_branch": "master",
            "open_issues_count": 0,
            "is_template": True,
            "topics": ["octocat", "atom", "electron", "api"],
            "has_issues": True,
            "has_projects": True,
            "has_wiki": True,
            "has_pages": False,
            "has_downloads": True,
            "archived": False,
            "disabled": False,
            "visibility": "public",
            "pushed_at": "2011-01-26T19:06:43Z",
            "created_at": "2011-01-26T19:01:12Z",
            "updated_at": "2011-01-26T19:14:43Z",
            "allow_rebase_merge": True,
            "template_repository": None,
            "temp_clone_token": "ABTLWHOULUVAXGTRYU7OC2876QJ2O",
            "allow_squash_merge": True,
            "allow_auto_merge": False,
            "delete_branch_on_merge": True,
            "allow_merge_commit": True,
            "subscribers_count": 42,
            "network_count": 0,
            "license": {
                "key": "mit",
                "name": "MIT License",
                "url": "https://api.github.com/licenses/mit",
                "spdx_id": "MIT",
                "node_id": "MDc6TGljZW5zZW1pdA==",
                "html_url": "https://github.com/licenses/mit",
            },
            "forks": 1,
            "open_issues": 1,
            "watchers": 1,
        }
    ],
}


PING_WEBHOOK_DATA = {
    "zen": "Non-blocking is better than blocking.",
    "hook_id": 100,
    "hook": {
        "type": "App",
        "id": 100,
        "name": "web",
        "active": True,
        "events": ["pull_request", "push"],
        "config": {
            "content_type": "json",
            "url": "http://127-0-0-1.sslip.io/api/connectors/github/webhook",
            "insecure_ssl": "0",
        },
        "updated_at": "2025-07-03T14:15:16Z",
        "created_at": "2025-07-03T14:15:16Z",
        "app_id": 1,
        "deliveries_url": "https://api.github.com/app/hook/deliveries",
    },
}


INSTALLATION_CREATED_WEBHOOK_DATA = {
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


class TestSetupGithubConnectorViewTests(AuthAPITestCase):

    @responses.activate
    def test_setup_connector_creates_github_app_sucessful(self):
        self.loginUser()
        github_api_pattern = re.compile(
            r"https:\/\/api\.github\.com\/app-manifests\/.*",
            re.IGNORECASE,
        )
        responses.add(
            responses.POST,
            url=github_api_pattern,
            status=status.HTTP_200_OK,
            json=MANIFEST_DATA,
        )

        params = {
            "code": generate_random_chars(10),
            "state": "create",
        }
        query_string = urlencode(params, doseq=True)
        response = self.client.get(
            reverse("git_connectors:github.setup"), QUERY_STRING=query_string
        )

        self.assertEqual(status.HTTP_303_SEE_OTHER, response.status_code)

        self.assertEqual(1, GitApp.objects.count())
        git_app: GitApp = GitApp.objects.first()  # type: ignore
        self.assertIsNotNone(git_app.github)

        github_app: GithubApp = git_app.github  # type: ignore
        self.assertEqual(MANIFEST_DATA["id"], github_app.app_id)
        self.assertEqual(MANIFEST_DATA["name"], github_app.name)
        self.assertEqual(MANIFEST_DATA["client_id"], github_app.client_id)
        self.assertEqual(MANIFEST_DATA["client_secret"], github_app.client_secret)
        self.assertEqual(MANIFEST_DATA["webhook_secret"], github_app.webhook_secret)
        self.assertEqual(MANIFEST_DATA["pem"], github_app.private_key)
        self.assertEqual(MANIFEST_DATA["html_url"], github_app.app_url)

        self.assertFalse(git_app.github.is_installed)  # type: ignore

    @responses.activate
    def test_setup_connector_install_github_app(self):
        self.loginUser()
        github_api_pattern = re.compile(
            r"https:\/\/api\.github\.com\/app-manifests\/.*",
            re.IGNORECASE,
        )
        responses.add(
            responses.POST,
            url=github_api_pattern,
            status=status.HTTP_200_OK,
            json=MANIFEST_DATA,
        )

        params = {
            "code": generate_random_chars(10),
            "state": "create",
        }
        query_string = urlencode(params, doseq=True)
        response = self.client.get(
            reverse("git_connectors:github.setup"), QUERY_STRING=query_string
        )

        self.assertEqual(status.HTTP_303_SEE_OTHER, response.status_code)

        git_app: GitApp = GitApp.objects.first()  # type: ignore
        github_app: GithubApp = git_app.github  # type: ignore

        params = {
            "code": generate_random_chars(10),
            "state": f"install:{github_app.id}",
            "installation_id": generate_random_chars(10),
        }
        query_string = urlencode(params, doseq=True)
        response = self.client.get(
            reverse("git_connectors:github.setup"), QUERY_STRING=query_string
        )

        self.assertEqual(status.HTTP_303_SEE_OTHER, response.status_code)

        github_app.refresh_from_db()
        self.assertTrue(git_app.github.is_installed)  # type: ignore

    def test_setup_connector_non_existent_gh_app(self):
        self.loginUser()

        params = {
            "code": generate_random_chars(10),
            "state": f"install:{GithubApp.ID_PREFIX}abcd12",
            "installation_id": generate_random_chars(10),
        }
        query_string = urlencode(params, doseq=True)
        response = self.client.get(
            reverse("git_connectors:github.setup"), QUERY_STRING=query_string
        )

        jprint(response.json())
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_setup_connector_install_with_no_installation_id(self):
        self.loginUser()

        params = {
            "code": generate_random_chars(10),
            "state": f"install:{GithubApp.ID_PREFIX}abcd12",
        }
        query_string = urlencode(params, doseq=True)
        response = self.client.get(
            reverse("git_connectors:github.setup"), QUERY_STRING=query_string
        )

        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    @responses.activate
    def test_setup_connector_creates_github_app_fails(self):
        self.loginUser()
        github_api_pattern = re.compile(
            r"https:\/\/api\.github\.com\/app-manifests\/.*",
            re.IGNORECASE,
        )
        responses.add(
            responses.POST,
            url=github_api_pattern,
            status=status.HTTP_404_NOT_FOUND,
            json={"data": "Page not found"},
        )

        params = {
            "code": generate_random_chars(10),
            "state": "create",
        }
        query_string = urlencode(params, doseq=True)
        response = self.client.get(
            reverse("git_connectors:github.setup"), QUERY_STRING=query_string
        )

        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

        self.assertEqual(0, GitApp.objects.count())
        self.assertEqual(0, GithubApp.objects.count())


class TestGithubWebhookAPIView(AuthAPITestCase):
    def test_github_webhook_respond_to_ping(self):
        self.loginUser()
        gh_app = GithubApp.objects.create(
            webhook_secret=MANIFEST_DATA["webhook_secret"],
            app_id=MANIFEST_DATA["id"],
            name=MANIFEST_DATA["name"],
            client_id=MANIFEST_DATA["client_id"],
            client_secret=MANIFEST_DATA["client_secret"],
            private_key=MANIFEST_DATA["pem"],
            app_url=MANIFEST_DATA["html_url"],
        )

        response = self.client.post(
            reverse("git_connectors:github.webhook"),
            data=PING_WEBHOOK_DATA,
            headers=get_signed_event_headers(
                GithubWebhookEvent.PING,
                PING_WEBHOOK_DATA,
                gh_app.webhook_secret,
            ),
        )

        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_github_webhook_validate_bad_signature(self):
        self.loginUser()
        GithubApp.objects.create(
            webhook_secret=MANIFEST_DATA["webhook_secret"],
            app_id=MANIFEST_DATA["id"],
            name=MANIFEST_DATA["name"],
            client_id=MANIFEST_DATA["client_id"],
            client_secret=MANIFEST_DATA["client_secret"],
            private_key=MANIFEST_DATA["pem"],
            app_url=MANIFEST_DATA["html_url"],
        )

        response = self.client.post(
            reverse("git_connectors:github.webhook"),
            data=PING_WEBHOOK_DATA,
            headers=get_signed_event_headers(
                "ping",
                PING_WEBHOOK_DATA,
                "fake",
            ),
        )

        jprint(response.json())
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_github_webhook_non_existent(self):
        self.loginUser()

        response = self.client.post(
            reverse("git_connectors:github.webhook"),
            data=PING_WEBHOOK_DATA,
            headers=get_signed_event_headers(
                "ping",
                PING_WEBHOOK_DATA,
                "fake",
            ),
        )

        jprint(response.json())
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_github_webhook_add_repositories_on_app_installation_webhook(self):
        self.loginUser()
        gh_app = GithubApp.objects.create(
            webhook_secret=MANIFEST_DATA["webhook_secret"],
            app_id=MANIFEST_DATA["id"],
            name=MANIFEST_DATA["name"],
            client_id=MANIFEST_DATA["client_id"],
            client_secret=MANIFEST_DATA["client_secret"],
            private_key=MANIFEST_DATA["pem"],
            app_url=MANIFEST_DATA["html_url"],
        )

        response = self.client.post(
            reverse("git_connectors:github.webhook"),
            data=INSTALLATION_CREATED_WEBHOOK_DATA,
            headers=get_signed_event_headers(
                GithubWebhookEvent.INSTALLATION,
                INSTALLATION_CREATED_WEBHOOK_DATA,
                gh_app.webhook_secret,
            ),
        )

        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(4, gh_app.repositories.count())
        print(gh_app.repositories.all())

    def test_github_webhook_add_repositories_on_app_installation_webhook_is_idempotent(
        self,
    ):
        self.loginUser()
        gh_app = GithubApp.objects.create(
            webhook_secret=MANIFEST_DATA["webhook_secret"],
            app_id=MANIFEST_DATA["id"],
            name=MANIFEST_DATA["name"],
            client_id=MANIFEST_DATA["client_id"],
            client_secret=MANIFEST_DATA["client_secret"],
            private_key=MANIFEST_DATA["pem"],
            app_url=MANIFEST_DATA["html_url"],
        )

        response = self.client.post(
            reverse("git_connectors:github.webhook"),
            data=INSTALLATION_CREATED_WEBHOOK_DATA,
            headers=get_signed_event_headers(
                GithubWebhookEvent.INSTALLATION,
                INSTALLATION_CREATED_WEBHOOK_DATA,
                gh_app.webhook_secret,
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        response = self.client.post(
            reverse("git_connectors:github.webhook"),
            data=INSTALLATION_CREATED_WEBHOOK_DATA,
            headers=get_signed_event_headers(
                GithubWebhookEvent.INSTALLATION,
                INSTALLATION_CREATED_WEBHOOK_DATA,
                gh_app.webhook_secret,
            ),
        )

        self.assertEqual(status.HTTP_200_OK, response.status_code)

        self.assertEqual(4, gh_app.repositories.count())
        print(gh_app.repositories.all())
