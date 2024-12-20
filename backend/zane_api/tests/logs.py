import datetime
import json
import uuid

from django.urls import reverse
from rest_framework import status
from django.conf import settings
import base64
import requests

from .base import AuthAPITestCase
from ..models import SimpleLog, DockerDeployment, DockerRegistryService, HttpLog
from django.conf import settings
from ..utils import jprint


class SimpleIngestCollectViewTests(AuthAPITestCase):
    def test_ingest_service_logs(self):
        p, service = self.create_and_deploy_redis_docker_service()

        deployment: DockerDeployment = service.deployments.first()

        simple_logs = [
            {
                "log": "1:C 30 Jun 2024 03:17:14.369 * oO0OoO0OoO0Oo Redis is starting oO0OoO0OoO0Oo",
                "container_id": "78dfe81bb4b3994eeb38f65f5a586084a2b4a649c0ab08b614d0f4c2cb499761",
                "container_name": "/srv-prj_ssbvBaqpbD7-srv_dkr_LeeCqAUZJnJ-dpl_dkr_KRbXo2FJput.1.zm0uncmx8w4wvnokdl6qxt55e",
                "time": "2024-07-01T03:17:14Z",
                "tag": json.dumps(
                    {
                        "deployment_id": deployment.hash,
                        "service_id": service.id,
                    }
                ),
                "source": "stdout",
            },
            {
                "log": "1:C 30 Jun 2024 03:17:14.369 * Redis version=7.2.5, bits=64, commit=00000000, modified=0, pid=1, just started",
                "container_id": "78dfe81bb4b3994eeb38f65f5a586084a2b4a649c0ab08b614d0f4c2cb499761",
                "container_name": "/srv-prj_ssbvBaqpbD7-srv_dkr_LeeCqAUZJnJ-dpl_dkr_KRbXo2FJput.1.zm0uncmx8w4wvnokdl6qxt55e",
                "time": "2024-06-30T03:17:14Z",
                "tag": json.dumps(
                    {
                        "deployment_id": deployment.hash,
                        "service_id": service.id,
                    }
                ),
                "source": "stdout",
            },
            {
                "log": "1:C 30 Jun 2024 03:17:14.369 * Configuration loaded",
                "container_id": "78dfe81bb4b3994eeb38f65f5a586084a2b4a649c0ab08b614d0f4c2cb499761",
                "container_name": "/srv-prj_ssbvBaqpbD7-srv_dkr_LeeCqAUZJnJ-dpl_dkr_KRbXo2FJput.1.zm0uncmx8w4wvnokdl6qxt55e",
                "time": "2024-06-30T03:17:14Z",
                "tag": json.dumps(
                    {
                        "deployment_id": deployment.hash,
                        "service_id": service.id,
                    }
                ),
                "source": "stdout",
            },
            {
                "log": "1:M 30 Jun 2024 03:17:14.369 * monotonic clock: POSIX clock_gettime",
                "container_id": "78dfe81bb4b3994eeb38f65f5a586084a2b4a649c0ab08b614d0f4c2cb499761",
                "container_name": "/srv-prj_ssbvBaqpbD7-srv_dkr_LeeCqAUZJnJ-dpl_dkr_KRbXo2FJput.1.zm0uncmx8w4wvnokdl6qxt55e",
                "time": "2024-06-30T03:17:14Z",
                "tag": json.dumps(
                    {
                        "deployment_id": deployment.hash,
                        "service_id": service.id,
                    }
                ),
                "source": "stdout",
            },
            {
                "log": "1:M 30 Jun 2024 03:17:14.371 * Running mode=standalone, port=6379.",
                "container_id": "78dfe81bb4b3994eeb38f65f5a586084a2b4a649c0ab08b614d0f4c2cb499761",
                "container_name": "/srv-prj_ssbvBaqpbD7-srv_dkr_LeeCqAUZJnJ-dpl_dkr_KRbXo2FJput.1.zm0uncmx8w4wvnokdl6qxt55e",
                "time": "2024-06-30T03:17:14Z",
                "tag": json.dumps(
                    {
                        "deployment_id": deployment.hash,
                        "service_id": service.id,
                    }
                ),
                "source": "stdout",
            },
            {
                "log": "1:M 30 Jun 2024 03:17:14.375 * Server initialized",
                "container_id": "78dfe81bb4b3994eeb38f65f5a586084a2b4a649c0ab08b614d0f4c2cb499761",
                "container_name": "/srv-prj_ssbvBaqpbD7-srv_dkr_LeeCqAUZJnJ-dpl_dkr_KRbXo2FJput.1.zm0uncmx8w4wvnokdl6qxt55e",
                "time": "2024-06-30T03:17:14Z",
                "tag": json.dumps(
                    {
                        "deployment_id": deployment.hash,
                        "service_id": service.id,
                    }
                ),
                "source": "stdout",
            },
            {
                "log": "1:M 30 Jun 2024 03:17:14.376 * Ready to accept connections tcp",
                "container_id": "78dfe81bb4b3994eeb38f65f5a586084a2b4a649c0ab08b614d0f4c2cb499761",
                "container_name": "/srv-prj_ssbvBaqpbD7-srv_dkr_LeeCqAUZJnJ-dpl_dkr_KRbXo2FJput.1.zm0uncmx8w4wvnokdl6qxt55e",
                "time": "2024-06-30T03:17:14Z",
                "tag": json.dumps(
                    {
                        "deployment_id": deployment.hash,
                        "service_id": service.id,
                    }
                ),
                "source": "stdout",
            },
        ]

        response = self.client.post(
            reverse("zane_api:logs.ingest"),
            data=simple_logs,
            headers={
                "Authorization": f"Basic {base64.b64encode(f'zaneops:{settings.SECRET_KEY}'.encode()).decode()}"
            },
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        response = requests.post(
            url=f"{settings.QUICKWIT_API_URL}/api/v1/{self.LOGS_INDEX_NAME}/search",
            json={
                "query": f"deployment_id:{deployment.hash}",
                "sort_by": "-created_at",
            },
        )
        deployment_logs = response.json()
        jprint(deployment_logs)

        self.assertEqual(len(simple_logs), deployment_logs["num_hits"])
        first_log = deployment_logs["hits"][0]
        self.assertEqual(
            simple_logs[0]["log"],
            first_log["content"],
        )
        self.assertIsNotNone(first_log["service_id"])


class SimpleLogViewTests(AuthAPITestCase):
    sample_log_contents = [
        (
            datetime.datetime(2024, 6, 30, 21, 52, 43, tzinfo=datetime.timezone.utc),
            '10.0.8.103 - - [30/Jun/2024:21:52:43 +0000] "GET / HTTP/1.1" 200 12127 "-" "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:127.0) Gecko/20100101 Firefox/127.0" "10.0.0.2"',
        ),
        (
            datetime.datetime(2024, 6, 30, 21, 52, 42, tzinfo=datetime.timezone.utc),
            '10.0.8.103 - - [30/Jun/2024:21:52:42 +0000] "GET / HTTP/1.1" 200 12127 "-" "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:127.0) Gecko/20100101 Firefox/127.0" "10.0.0.2"',
        ),
        (
            datetime.datetime(2024, 6, 30, 21, 52, 39, tzinfo=datetime.timezone.utc),
            '10.0.8.103 - - [30/Jun/2024:21:52:39 +0000] "GET / HTTP/1.1" 200 12127 "-" "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:127.0) Gecko/20100101 Firefox/127.0" "10.0.0.2"',
        ),
        (
            datetime.datetime(2024, 6, 30, 21, 52, 37, tzinfo=datetime.timezone.utc),
            '10.0.8.103 - - [30/Jun/2024:21:52:37 +0000] "GET / HTTP/1.1" 200 12127 "-" "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:127.0) Gecko/20100101 Firefox/127.0" "10.0.0.2"',
        ),
        (
            datetime.datetime(2024, 6, 30, 21, 52, 34, tzinfo=datetime.timezone.utc),
            '10.0.8.103 - - [30/Jun/2024:21:52:34 +0000] "GET / HTTP/1.1" 200 12127 "-" "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:127.0) Gecko/20100101 Firefox/127.0" "10.0.0.2"',
        ),
        (
            datetime.datetime(2024, 6, 30, 21, 52, 32, tzinfo=datetime.timezone.utc),
            '10.0.8.103 - - [30/Jun/2024:21:52:32 +0000] "GET / HTTP/1.1" 200 12127 "-" "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:127.0) Gecko/20100101 Firefox/127.0" "10.0.0.2"',
        ),
        (
            datetime.datetime(2024, 6, 30, 21, 52, 29, tzinfo=datetime.timezone.utc),
            '10.0.8.103 - - [30/Jun/2024:21:52:29 +0000] "GET / HTTP/1.1" 200 12127 "-" "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:127.0) Gecko/20100101 Firefox/127.0" "10.0.0.2"',
        ),
        (
            datetime.datetime(2024, 6, 30, 21, 52, 27, tzinfo=datetime.timezone.utc),
            '10.0.8.103 - - [30/Jun/2024:21:52:27 +0000] "GET / HTTP/1.1" 200 12127 "-" "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:127.0) Gecko/20100101 Firefox/127.0" "10.0.0.2"',
        ),
        (
            datetime.datetime(2024, 6, 30, 21, 52, 24, tzinfo=datetime.timezone.utc),
            '10.0.8.103 - - [30/Jun/2024:21:52:24 +0000] "GET / HTTP/1.1" 200 12127 "-" "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:127.0) Gecko/20100101 Firefox/127.0" "10.0.0.2"',
        ),
        (
            datetime.datetime(2024, 6, 30, 21, 52, 22, tzinfo=datetime.timezone.utc),
            '10.0.8.103 - - [30/Jun/2024:21:52:22 +0000] "GET / HTTP/1.1" 200 12127 "-" "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:127.0) Gecko/20100101 Firefox/127.0" "10.0.0.2"',
        ),
        (
            datetime.datetime(2024, 12, 30, 21, 52, 43, tzinfo=datetime.timezone.utc),
            '{"level":"info","ts":1734635931.911247,"logger":"http.log.access","msg":"handled request","request":{"remote_ip":"10.0.1.57","remote_port":"59916","client_ip":"10.0.1.57","proto":"HTTP/1.1","method":"GET","host":"sandbox-caddy-demo-docker.127-0-0-1.sslip.io","uri":"/","headers":{"Upgrade-Insecure-Requests":["1"],"X-Request-Id":["04f1b598-fb0b-49ca-bbf5-6cd70ad305e8"],"Accept":["text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"],"Dnt":["1"],"Accept-Encoding":["gzip, deflate"],"Sec-Gpc":["1"],"X-Forwarded-Host":["sandbox-caddy-demo-docker.127-0-0-1.sslip.io"],"Priority":["u=0, i"],"Referer":["http://sandbox-caddy-demo-docker.127-0-0-1.sslip.io/api-reference/openapi/"],"X-Forwarded-For":["10.0.0.2"],"X-Forwarded-Proto":["http"],"User-Agent":["Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0"],"Accept-Language":["en-GB,en-US;q=0.8,fr;q=0.5,fr-FR;q=0.3"],"Cookie":["REDACTED"]}},"bytes_read":0,"user_id":"","duration":0.002727297,"size":29996,"status":200,"resp_headers":{"Server":["Caddy"],"Vary":["Accept-Encoding"],"Etag":["\\"d5ztbs3p8mbkn58\\""],"Content-Type":["text/html; charset=utf-8"],"Last-Modified":["Sat, 30 Nov 2024 20:57:56 GMT"],"Accept-Ranges":["bytes"],"Content-Length":["29996"]}}',
        ),
        (
            datetime.datetime(2024, 12, 30, 21, 52, 43, tzinfo=datetime.timezone.utc),
            '{"level":"info","ts":1734635927.307818,"logger":"http.log.access","msg":"handled request","request":{"remote_ip":"10.0.1.57","remote_port":"59916","client_ip":"10.0.1.57","proto":"HTTP/1.1","method":"GET","host":"sandbox-caddy-demo-docker.127-0-0-1.sslip.io","uri":"/api-reference/openapi/","headers":{"Upgrade-Insecure-Requests":["1"],"X-Forwarded-For":["10.0.0.2"],"X-Request-Id":["4e490c1d-06d4-494c-940d-a47580ee7be4"],"Dnt":["1"],"Referer":["http://sandbox-caddy-demo-docker.127-0-0-1.sslip.io/screenshots/"],"User-Agent":["Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0"],"Accept-Language":["en-GB,en-US;q=0.8,fr;q=0.5,fr-FR;q=0.3"],"Accept":["text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"],"Accept-Encoding":["gzip, deflate"],"Cookie":["REDACTED"],"X-Forwarded-Proto":["http"],"Priority":["u=0, i"],"Sec-Gpc":["1"],"X-Forwarded-Host":["sandbox-caddy-demo-docker.127-0-0-1.sslip.io"]}},"bytes_read":0,"user_id":"","duration":0.000806585,"size":2632,"status":200,"resp_headers":{"Content-Type":["text/html; charset=utf-8"],"Last-Modified":["Sat, 30 Nov 2024 20:57:54 GMT"],"Accept-Ranges":["bytes"],"Content-Length":["2632"],"Server":["Caddy"],"Vary":["Accept-Encoding"],"Etag":["\\"d5ztbr6mhog0214\\""]}}',
        ),
        (
            datetime.datetime(2024, 12, 30, 21, 52, 43, tzinfo=datetime.timezone.utc),
            '{"level":"info","ts":1734635927.2966347,"logger":"http.log.access","msg":"handled request","request":{"remote_ip":"10.0.1.57","remote_port":"59916","client_ip":"10.0.1.57","proto":"HTTP/1.1","method":"GET","host":"sandbox-caddy-demo-docker.127-0-0-1.sslip.io","uri":"/api-reference/openapi","headers":{"Accept":["text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"],"X-Forwarded-For":["10.0.0.2"],"X-Forwarded-Proto":["http"],"Sec-Gpc":["1"],"X-Forwarded-Host":["sandbox-caddy-demo-docker.127-0-0-1.sslip.io"],"User-Agent":["Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0"],"Accept-Encoding":["gzip, deflate"],"Cookie":["REDACTED"],"Priority":["u=0, i"],"Upgrade-Insecure-Requests":["1"],"X-Request-Id":["b1299d8f-6992-47a9-ad3d-e8748f1b78ef"],"Accept-Language":["en-GB,en-US;q=0.8,fr;q=0.5,fr-FR;q=0.3"],"Dnt":["1"],"Referer":["http://sandbox-caddy-demo-docker.127-0-0-1.sslip.io/screenshots/"]}},"bytes_read":0,"user_id":"","duration":0.000334876,"size":59,"status":308,"resp_headers":{"Server":["Caddy"],"Location":["/api-reference/openapi/"],"Content-Type":["text/html; charset=utf-8"]}}',
        ),
        (
            datetime.datetime(2024, 12, 30, 21, 52, 43, tzinfo=datetime.timezone.utc),
            '{"level":"info","ts":1734635926.830525,"logger":"http.log.access","msg":"handled request","request":{"remote_ip":"10.0.1.57","remote_port":"59916","client_ip":"10.0.1.57","proto":"HTTP/1.1","method":"GET","host":"sandbox-caddy-demo-docker.127-0-0-1.sslip.io","uri":"/images/logs-max-light.png","headers":{"X-Forwarded-Proto":["http"],"X-Forwarded-For":["10.0.0.2"],"Priority":["u=5, i"],"Sec-Gpc":["1"],"User-Agent":["Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0"],"Dnt":["1"],"Referer":["http://sandbox-caddy-demo-docker.127-0-0-1.sslip.io/screenshots/"],"Accept-Encoding":["gzip, deflate"],"Accept":["image/avif,image/webp,image/png,image/svg+xml,image/*;q=0.8,*/*;q=0.5"],"Accept-Language":["en-GB,en-US;q=0.8,fr;q=0.5,fr-FR;q=0.3"],"Cookie":["REDACTED"],"X-Forwarded-Host":["sandbox-caddy-demo-docker.127-0-0-1.sslip.io"],"X-Request-Id":["c9d6b730-f48b-4fb4-8296-7c4189851e3b"]}},"bytes_read":0,"user_id":"","duration":0.032420153,"size":1329945,"status":200,"resp_headers":{"Last-Modified":["Sat, 30 Nov 2024 20:57:53 GMT"],"Accept-Ranges":["bytes"],"Content-Length":["1329945"],"Server":["Caddy"],"Cache-Control":["public, max-age=31536000, immutable"],"Vary":["Accept-Encoding"],"Etag":["\\"d5ztbqq347i8si6x\\""],"Content-Type":["image/png"]}}',
        ),
        (
            datetime.datetime(2024, 12, 30, 21, 52, 43, tzinfo=datetime.timezone.utc),
            '{"level":"info","ts":1734635926.824431,"logger":"http.log.access","msg":"handled request","request":{"remote_ip":"10.0.1.57","remote_port":"59866","client_ip":"10.0.1.57","proto":"HTTP/1.1","method":"GET","host":"sandbox-caddy-demo-docker.127-0-0-1.sslip.io","uri":"/images/logs-rainbow-light.png","headers":{"Sec-Gpc":["1"],"X-Forwarded-Host":["sandbox-caddy-demo-docker.127-0-0-1.sslip.io"],"User-Agent":["Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0"],"Accept":["image/avif,image/webp,image/png,image/svg+xml,image/*;q=0.8,*/*;q=0.5"],"Dnt":["1"],"X-Request-Id":["f8cec7bb-200c-42d1-b7de-a3fc8c4a3bde"],"X-Forwarded-For":["10.0.0.2"],"X-Forwarded-Proto":["http"],"Accept-Encoding":["gzip, deflate"],"Accept-Language":["en-GB,en-US;q=0.8,fr;q=0.5,fr-FR;q=0.3"],"Cookie":["REDACTED"],"Priority":["u=5, i"],"Referer":["http://sandbox-caddy-demo-docker.127-0-0-1.sslip.io/screenshots/"]}},"bytes_read":0,"user_id":"","duration":0.027112225,"size":1352496,"status":200,"resp_headers":{"Vary":["Accept-Encoding"],"Etag":["\\"d5ztbqq347i8szlc\\""],"Content-Type":["image/png"],"Last-Modified":["Sat, 30 Nov 2024 20:57:53 GMT"],"Accept-Ranges":["bytes"],"Content-Length":["1352496"],"Server":["Caddy"],"Cache-Control":["public, max-age=31536000, immutable"]}}',
        ),
    ]

    def test_view_logs(self):
        p, service = self.create_and_deploy_redis_docker_service()
        deployment: DockerDeployment = service.deployments.first()

        # Insert logs
        simple_logs = [
            {
                "log": content,
                "container_id": "78dfe81bb4b3994eeb38f65f5a586084a2b4a649c0ab08b614d0f4c2cb499761",
                "container_name": "/srv-prj_ssbvBaqpbD7-srv_dkr_LeeCqAUZJnJ-dpl_dkr_KRbXo2FJput.1.zm0uncmx8w4wvnokdl6qxt55e",
                "time": time.isoformat(),
                "tag": json.dumps(
                    {
                        "deployment_id": deployment.hash,
                        "service_id": service.id,
                    }
                ),
                "source": "stdout" if i % 2 == 0 else "stderr",
            }
            for i, (time, content) in enumerate(self.sample_log_contents)
        ]
        response = self.client.post(
            reverse("zane_api:logs.ingest"),
            data=simple_logs,
            headers={
                "Authorization": f"Basic {base64.b64encode(f'zaneops:{settings.SECRET_KEY}'.encode()).decode()}"
            },
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # Make HTTP request
        response = self.client.get(
            reverse(
                "zane_api:services.docker.deployment_logs",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": service.slug,
                    "deployment_hash": deployment.hash,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(len(simple_logs), len(response.json()["results"]))

    def test_paginate(self):
        p, service = self.create_and_deploy_redis_docker_service()
        deployment: DockerDeployment = service.deployments.first()

        # Insert logs
        simple_logs = [
            {
                "log": content,
                "container_id": "78dfe81bb4b3994eeb38f65f5a586084a2b4a649c0ab08b614d0f4c2cb499761",
                "container_name": "/srv-prj_ssbvBaqpbD7-srv_dkr_LeeCqAUZJnJ-dpl_dkr_KRbXo2FJput.1.zm0uncmx8w4wvnokdl6qxt55e",
                "time": time.isoformat(),
                "tag": json.dumps(
                    {
                        "deployment_id": deployment.hash,
                        "service_id": service.id,
                    }
                ),
                "source": "stdout" if i % 2 == 0 else "stderr",
            }
            for i, (time, content) in enumerate(self.sample_log_contents)
        ]
        response = self.client.post(
            reverse("zane_api:logs.ingest"),
            data=simple_logs,
            headers={
                "Authorization": f"Basic {base64.b64encode(f'zaneops:{settings.SECRET_KEY}'.encode()).decode()}"
            },
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        response = self.client.get(
            reverse(
                "zane_api:services.docker.deployment_logs",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": service.slug,
                    "deployment_hash": deployment.hash,
                },
            ),
            QUERY_STRING="per_page=5",
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        data = response.json()
        self.assertEqual(5, len(data["results"]))
        self.assertIsNotNone(data["next"])

    def test_paginate_get_next_page(self):
        p, service = self.create_and_deploy_redis_docker_service()
        deployment: DockerDeployment = service.deployments.first()

        # Insert logs
        simple_logs = [
            {
                "log": content,
                "container_id": "78dfe81bb4b3994eeb38f65f5a586084a2b4a649c0ab08b614d0f4c2cb499761",
                "container_name": "/srv-prj_ssbvBaqpbD7-srv_dkr_LeeCqAUZJnJ-dpl_dkr_KRbXo2FJput.1.zm0uncmx8w4wvnokdl6qxt55e",
                "time": time.isoformat(),
                "tag": json.dumps(
                    {
                        "deployment_id": deployment.hash,
                        "service_id": service.id,
                    }
                ),
                "source": "stdout" if i % 2 == 0 else "stderr",
            }
            for i, (time, content) in enumerate(self.sample_log_contents)
        ]
        response = self.client.post(
            reverse("zane_api:logs.ingest"),
            data=simple_logs,
            headers={
                "Authorization": f"Basic {base64.b64encode(f'zaneops:{settings.SECRET_KEY}'.encode()).decode()}"
            },
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        response = self.client.get(
            reverse(
                "zane_api:services.docker.deployment_logs",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": service.slug,
                    "deployment_hash": deployment.hash,
                },
            ),
            QUERY_STRING="per_page=5",
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        first_page = response.json()
        self.assertEqual(5, len(first_page["results"]))
        next_cursor = first_page["next"]
        self.assertIsNotNone(first_page["next"])

        response = self.client.get(
            reverse(
                "zane_api:services.docker.deployment_logs",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": service.slug,
                    "deployment_hash": deployment.hash,
                },
            ),
            QUERY_STRING=f"per_page=5&cursor={next_cursor}",
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        second_page = response.json()
        self.assertEqual(5, len(second_page["results"]))
        # Check that no item from first page appears in second page
        first_page_contents = {item["id"] for item in first_page["results"]}
        second_page_contents = {item["id"] for item in second_page["results"]}
        self.assertEqual(0, len(first_page_contents.intersection(second_page_contents)))

    def test_paginate_get_previous_page(self):
        p, service = self.create_and_deploy_redis_docker_service()
        deployment: DockerDeployment = service.deployments.first()

        # Insert logs
        simple_logs = [
            {
                "log": content,
                "container_id": "78dfe81bb4b3994eeb38f65f5a586084a2b4a649c0ab08b614d0f4c2cb499761",
                "container_name": "/srv-prj_ssbvBaqpbD7-srv_dkr_LeeCqAUZJnJ-dpl_dkr_KRbXo2FJput.1.zm0uncmx8w4wvnokdl6qxt55e",
                "time": time.isoformat(),
                "tag": json.dumps(
                    {
                        "deployment_id": deployment.hash,
                        "service_id": service.id,
                    }
                ),
                "source": "stdout" if i % 2 == 0 else "stderr",
            }
            for i, (time, content) in enumerate(self.sample_log_contents)
        ]
        response = self.client.post(
            reverse("zane_api:logs.ingest"),
            data=simple_logs,
            headers={
                "Authorization": f"Basic {base64.b64encode(f'zaneops:{settings.SECRET_KEY}'.encode()).decode()}"
            },
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # Get first page
        response = self.client.get(
            reverse(
                "zane_api:services.docker.deployment_logs",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": service.slug,
                    "deployment_hash": deployment.hash,
                },
            ),
            QUERY_STRING="per_page=5",
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        first_page = response.json()
        self.assertEqual(5, len(first_page["results"]))

        # Get second page
        next_cursor = first_page["next"]
        response = self.client.get(
            reverse(
                "zane_api:services.docker.deployment_logs",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": service.slug,
                    "deployment_hash": deployment.hash,
                },
            ),
            QUERY_STRING=f"per_page=5&cursor={next_cursor}",
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        second_page = response.json()
        previous_cursor = second_page["previous"]
        self.assertEqual(5, len(second_page["results"]))
        self.assertIsNotNone(second_page["previous"])

        # Get previous page
        response = self.client.get(
            reverse(
                "zane_api:services.docker.deployment_logs",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": service.slug,
                    "deployment_hash": deployment.hash,
                },
            ),
            QUERY_STRING=f"per_page=5&cursor={previous_cursor}",
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        previous_page = response.json()
        self.assertEqual(first_page["results"], previous_page["results"])

    def test_complex_filter(self):
        p, service = self.create_and_deploy_redis_docker_service()
        deployment: DockerDeployment = service.deployments.first()

        # Insert logs
        simple_logs = [
            {
                "log": content,
                "container_id": "78dfe81bb4b3994eeb38f65f5a586084a2b4a649c0ab08b614d0f4c2cb499761",
                "container_name": "/srv-prj_ssbvBaqpbD7-srv_dkr_LeeCqAUZJnJ-dpl_dkr_KRbXo2FJput.1.zm0uncmx8w4wvnokdl6qxt55e",
                "time": time.isoformat(),
                "tag": json.dumps(
                    {
                        "deployment_id": deployment.hash,
                        "service_id": service.id,
                    }
                ),
                "source": "stdout" if i % 2 == 0 else "stderr",
            }
            for i, (time, content) in enumerate(self.sample_log_contents)
        ]
        response = self.client.post(
            reverse("zane_api:logs.ingest"),
            data=simple_logs,
            headers={
                "Authorization": f"Basic {base64.b64encode(f'zaneops:{settings.SECRET_KEY}'.encode()).decode()}"
            },
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        time_after = datetime.datetime(
            2024, 6, 30, 21, 52, 37, tzinfo=datetime.timezone.utc
        )
        time_before = datetime.datetime(
            2024, 6, 30, 21, 52, 43, tzinfo=datetime.timezone.utc
        )
        response = self.client.get(
            reverse(
                "zane_api:services.docker.deployment_logs",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": service.slug,
                    "deployment_hash": deployment.hash,
                },
            ),
            QUERY_STRING=f"level=ERROR&time_after={time_after.strftime('%Y-%m-%dT%H:%M:%SZ')}&time_before={time_before.strftime('%Y-%m-%dT%H:%M:%SZ')}",
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(2, len(response.json()["results"]))

    def test_quote_in_query(self):
        p, service = self.create_and_deploy_redis_docker_service()
        deployment: DockerDeployment = service.deployments.first()

        SimpleLog.objects.bulk_create(
            [
                SimpleLog(
                    time=time,
                    content=content,
                    service_id=service.id,
                    deployment_id=deployment.hash,
                    source=SimpleLog.LogSource.SERVICE,
                    content_text=SimpleLog.escape_ansi(content),
                    level=SimpleLog.LogLevel.INFO,
                )
                for (time, content) in self.sample_log_contents
            ]
        )

        response = self.client.get(
            reverse(
                "zane_api:services.docker.deployment_logs",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": service.slug,
                    "deployment_hash": deployment.hash,
                },
            ),
            QUERY_STRING=f"content=%2B0000%5D%20%22POST",  # searching for `+0000] "POST`
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(1, len(response.json()["results"]))

    async def test_delete_logs_after_archiving_a_service(self):
        p, service = await self.acreate_and_deploy_redis_docker_service()
        deployment: DockerDeployment = await service.deployments.afirst()

        await SimpleLog.objects.abulk_create(
            [
                SimpleLog(
                    time=time,
                    content=content,
                    service_id=service.id,
                    deployment_id=deployment.hash,
                    source=SimpleLog.LogSource.SERVICE,
                    content_text=SimpleLog.escape_ansi(content),
                    level=SimpleLog.LogLevel.INFO,
                )
                for (time, content) in self.sample_log_contents
            ]
        )

        response = await self.async_client.delete(
            reverse(
                "zane_api:services.docker.archive",
                kwargs={"project_slug": p.slug, "service_slug": service.slug},
            ),
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)
        deleted_service = await DockerRegistryService.objects.filter(
            slug=service.slug
        ).afirst()
        self.assertIsNone(deleted_service)

        logs_for_service = await SimpleLog.objects.filter(
            service_id=service.id
        ).acount()
        self.assertEqual(0, logs_for_service)


class HttpLogViewTests(AuthAPITestCase):
    sample_log_entries = [
        {
            "level": "info",
            "ts": 1721578245.8976514,
            "logger": "http.log.access",
            "msg": "handled request",
            "request": {
                "remote_ip": "10.0.0.2",
                "remote_port": "33632",
                "client_ip": "10.0.0.2",
                "proto": "HTTP/1.1",
                "method": "GET",
                "host": "nginx-demo.zaneops.local",
                "uri": "/docs?query",
                "headers": {
                    "Upgrade-Insecure-Requests": ["1"],
                    "Accept-Language": ["en,en-US;q=0.8,fr;q=0.5,fr-FR;q=0.3"],
                    "Cookie": ["REDACTED"],
                    "Dnt": ["1"],
                    "Connection": ["keep-alive"],
                    "Sec-Gpc": ["1"],
                    "Priority": ["u=0, i"],
                    "User-Agent": [
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:128.0) Gecko/20100101 Firefox/128.0"
                    ],
                    "Accept": [
                        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/png,image/svg+xml,*/*;q=0.8"
                    ],
                    "Accept-Encoding": ["gzip, deflate"],
                },
            },
            "bytes_read": 0,
            "user_id": "",
            "duration": 0.006841144,
            "size": 12119,
            "status": 200,
            "resp_headers": {
                "Content-Type": ["text/html"],
                "Expires": ["Sun, 21 Jul 2024 16:10:44 GMT"],
                "Server": ["Caddy", "nginx/1.27.0"],
                "Alt-Svc": ['h3=":443"; ma=2592000'],
                "Cache-Control": ["no-cache"],
                "Date": ["Sun, 21 Jul 2024 16:10:45 GMT"],
            },
        },
        {
            "level": "info",
            "ts": 1721578227.3117847,
            "logger": "http.log.access",
            "msg": "handled request",
            "request": {
                "remote_ip": "10.0.0.2",
                "remote_port": "47142",
                "client_ip": "10.0.0.2",
                "proto": "HTTP/1.1",
                "method": "POST",
                "host": "nginx-demo.zaneops.local",
                "uri": "/abc?a=c",
                "headers": {
                    "Content-Length": ["0"],
                    "User-Agent": ["HTTPie"],
                    "Connection": ["close"],
                },
            },
            "bytes_read": 0,
            "user_id": "",
            "duration": 0.006406094,
            "size": 157,
            "status": 405,
            "resp_headers": {
                "Server": ["Caddy", "nginx/1.27.0"],
                "Alt-Svc": ['h3=":443"; ma=2592000'],
                "Date": ["Sun, 21 Jul 2024 16:10:27 GMT"],
                "Content-Type": ["text/html"],
            },
        },
        {
            "level": "info",
            "ts": 1721578160.8126135,
            "logger": "http.log.access",
            "msg": "handled request",
            "request": {
                "remote_ip": "10.0.0.2",
                "remote_port": "33632",
                "client_ip": "10.0.0.2",
                "proto": "HTTP/1.1",
                "method": "GET",
                "host": "nginx-demo.zaneops.local",
                "uri": "/docs",
                "headers": {
                    "User-Agent": [
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:128.0) Gecko/20100101 Firefox/128.0"
                    ],
                    "Accept": [
                        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/png,image/svg+xml,*/*;q=0.8"
                    ],
                    "Dnt": ["1"],
                    "Connection": ["keep-alive"],
                    "Accept-Language": ["en,en-US;q=0.8,fr;q=0.5,fr-FR;q=0.3"],
                    "Accept-Encoding": ["gzip, deflate"],
                    "Cookie": ["REDACTED"],
                    "Upgrade-Insecure-Requests": ["1"],
                    "Sec-Gpc": ["1"],
                    "Priority": ["u=0, i"],
                },
            },
            "bytes_read": 0,
            "user_id": "",
            "duration": 0.010405301,
            "size": 12113,
            "status": 200,
            "resp_headers": {
                "Date": ["Sun, 21 Jul 2024 16:09:20 GMT"],
                "Content-Type": ["text/html"],
                "Server": ["Caddy", "nginx/1.27.0"],
                "Alt-Svc": ['h3=":443"; ma=2592000'],
                "Expires": ["Sun, 21 Jul 2024 16:09:19 GMT"],
                "Cache-Control": ["no-cache"],
            },
        },
        {
            "level": "info",
            "ts": 1721578161.903769,
            "logger": "http.log.access",
            "msg": "handled request",
            "request": {
                "remote_ip": "10.0.0.2",
                "remote_port": "33632",
                "client_ip": "10.0.0.2",
                "proto": "HTTP/1.1",
                "method": "GET",
                "host": "nginx-demo.zaneops.local",
                "uri": "/docs",
                "headers": {
                    "Accept-Encoding": ["gzip, deflate"],
                    "Connection": ["keep-alive"],
                    "Priority": ["u=0, i"],
                    "User-Agent": [
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:128.0) Gecko/20100101 Firefox/128.0"
                    ],
                    "Accept": [
                        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/png,image/svg+xml,*/*;q=0.8"
                    ],
                    "Upgrade-Insecure-Requests": ["1"],
                    "Sec-Gpc": ["1"],
                    "Accept-Language": ["en,en-US;q=0.8,fr;q=0.5,fr-FR;q=0.3"],
                    "Dnt": ["1"],
                    "Cookie": ["REDACTED"],
                },
            },
            "bytes_read": 0,
            "user_id": "",
            "duration": 0.001357747,
            "size": 12113,
            "status": 200,
            "resp_headers": {
                "Expires": ["Sun, 21 Jul 2024 16:09:20 GMT"],
                "Cache-Control": ["no-cache"],
                "Date": ["Sun, 21 Jul 2024 16:09:21 GMT"],
                "Server": ["Caddy", "nginx/1.27.0"],
                "Alt-Svc": ['h3=":443"; ma=2592000'],
                "Content-Type": ["text/html"],
            },
        },
        {
            "level": "info",
            "ts": 1721578015.8651662,
            "logger": "http.log.access",
            "msg": "handled request",
            "request": {
                "remote_ip": "10.0.0.2",
                "remote_port": "53524",
                "client_ip": "10.0.0.2",
                "proto": "HTTP/1.1",
                "method": "GET",
                "host": "nginx-demo.zaneops.local",
                "uri": "/docs",
                "headers": {
                    "Upgrade-Insecure-Requests": ["1"],
                    "Accept-Language": ["en,en-US;q=0.8,fr;q=0.5,fr-FR;q=0.3"],
                    "Accept-Encoding": ["gzip, deflate"],
                    "Connection": ["keep-alive"],
                    "Cookie": ["REDACTED"],
                    "User-Agent": [
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:128.0) Gecko/20100101 Firefox/128.0"
                    ],
                    "Accept": [
                        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/png,image/svg+xml,*/*;q=0.8"
                    ],
                    "Dnt": ["1"],
                    "Sec-Gpc": ["1"],
                    "Priority": ["u=0, i"],
                },
            },
            "bytes_read": 0,
            "user_id": "",
            "duration": 0.007462656,
            "size": 12113,
            "status": 200,
            "resp_headers": {
                "Date": ["Sun, 21 Jul 2024 16:06:55 GMT"],
                "Content-Type": ["text/html"],
                "Server": ["Caddy", "nginx/1.27.0"],
                "Alt-Svc": ['h3=":443"; ma=2592000'],
                "Expires": ["Sun, 21 Jul 2024 16:06:54 GMT"],
                "Cache-Control": ["no-cache"],
            },
        },
        {
            "level": "info",
            "ts": 1721612466.7106614,
            "logger": "http.log.access",
            "msg": "handled request",
            "request": {
                "remote_ip": "10.0.0.2",
                "remote_port": "57224",
                "client_ip": "10.0.0.2",
                "proto": "HTTP/1.1",
                "method": "GET",
                "host": "nginx-demo.zaneops.local",
                "uri": "/docs?query",
                "headers": {
                    "Cookie": ["REDACTED"],
                    "Upgrade-Insecure-Requests": ["1"],
                    "Dnt": ["1"],
                    "Connection": ["keep-alive"],
                    "Sec-Gpc": ["1"],
                    "User-Agent": [
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:128.0) Gecko/20100101 Firefox/128.0"
                    ],
                    "Accept": [
                        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/png,image/svg+xml,*/*;q=0.8"
                    ],
                    "Accept-Language": ["en,en-US;q=0.8,fr;q=0.5,fr-FR;q=0.3"],
                    "Accept-Encoding": ["gzip, deflate"],
                    "Priority": ["u=0, i"],
                },
            },
            "bytes_read": 0,
            "user_id": "",
            "duration": 0.009803894,
            "size": 12123,
            "status": 200,
            "resp_headers": {
                "Server": ["Caddy", "nginx/1.27.0"],
                "Alt-Svc": ['h3=":443"; ma=2592000'],
                "Content-Type": ["text/html"],
                "Expires": ["Mon, 22 Jul 2024 01:41:05 GMT"],
                "Cache-Control": ["no-cache"],
                "Date": ["Mon, 22 Jul 2024 01:41:06 GMT"],
            },
        },
    ]

    def test_view_logs(self):
        p, service = self.create_and_deploy_caddy_docker_service()

        fist_deployment: DockerDeployment = service.deployments.first()

        simple_proxy_logs = [
            {
                "source": "stdout",
                "container_id": "8320676fc77bb91b54f0dff7015c08148fd3021db7038c8d0c18ec7378e1979e",
                "log": json.dumps(
                    {
                        **log,
                        "zane_deployment_upstream": f"{fist_deployment.network_aliases[-1]}:80",
                        "zane_deployment_green_hash": None,
                        "zane_deployment_blue_hash": fist_deployment.hash,
                        "zane_service_id": service.id,
                        "uuid": str(uuid.uuid4()),
                    }
                ),
                "container_name": "/zane_proxy.1.kj2d879vqbnpishh4d66i47do",
                "time": "2024-06-25T14:16:25+0000",
                "service": "proxy",
                "tag": json.dumps({"service_id": "zane.proxy"}),
            }
            for log in self.sample_log_entries
        ]

        response = self.client.post(
            reverse("zane_api:logs.ingest"),
            data=simple_proxy_logs,
            headers={
                "Authorization": f"Basic {base64.b64encode(f'zaneops:{settings.SECRET_KEY}'.encode()).decode()}"
            },
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        response = self.client.get(
            reverse(
                "zane_api:services.docker.deployment_http_logs",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": service.slug,
                    "deployment_hash": fist_deployment.hash,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(len(simple_proxy_logs), len(response.json()["results"]))

    def test_filter(self):
        p, service = self.create_and_deploy_caddy_docker_service()

        fist_deployment: DockerDeployment = service.deployments.first()

        simple_proxy_logs = [
            {
                "source": "stdout",
                "container_id": "8320676fc77bb91b54f0dff7015c08148fd3021db7038c8d0c18ec7378e1979e",
                "log": json.dumps(
                    {
                        **log,
                        "zane_deployment_upstream": f"{fist_deployment.network_aliases[-1]}:80",
                        "zane_deployment_green_hash": None,
                        "zane_deployment_blue_hash": fist_deployment.hash,
                        "zane_service_id": service.id,
                        "uuid": str(uuid.uuid4()),
                    }
                ),
                "container_name": "/zane_proxy.1.kj2d879vqbnpishh4d66i47do",
                "time": "2024-06-25T14:16:25+0000",
                "service": "proxy",
                "tag": json.dumps({"service_id": "zane.proxy"}),
            }
            for log in self.sample_log_entries
        ]

        response = self.client.post(
            reverse("zane_api:logs.ingest"),
            headers={
                "Authorization": f"Basic {base64.b64encode(f'zaneops:{settings.SECRET_KEY}'.encode()).decode()}"
            },
            data=simple_proxy_logs,
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        response = self.client.get(
            reverse(
                "zane_api:services.docker.deployment_http_logs",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": service.slug,
                    "deployment_hash": fist_deployment.hash,
                },
            ),
            QUERY_STRING=f"request_path=/abc&request_method=POST",
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(1, len(response.json()["results"]))


class HTTPLogCollectViewTests(AuthAPITestCase):
    sample_log_entries = [
        {
            "level": "info",
            "ts": 1721578245.8976514,
            "logger": "http.log.access",
            "msg": "handled request",
            "request": {
                "remote_ip": "10.0.0.2",
                "remote_port": "33632",
                "client_ip": "10.0.0.2",
                "proto": "HTTP/2.0",
                "method": "GET",
                "host": "nginx-demo.zaneops.local",
                "uri": "/docs?query",
                "headers": {
                    "Upgrade-Insecure-Requests": ["1"],
                    "Accept-Language": ["en,en-US;q=0.8,fr;q=0.5,fr-FR;q=0.3"],
                    "Cookie": ["REDACTED"],
                    "Dnt": ["1"],
                    "Connection": ["keep-alive"],
                    "Sec-Gpc": ["1"],
                    "Priority": ["u=0, i"],
                    "User-Agent": [
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:128.0) Gecko/20100101 Firefox/128.0"
                    ],
                    "Accept": [
                        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/png,image/svg+xml,*/*;q=0.8"
                    ],
                    "Accept-Encoding": ["gzip, deflate"],
                },
            },
            "bytes_read": 0,
            "user_id": "",
            "duration": 252.619561756,
            "size": 12119,
            "status": 200,
            "resp_headers": {
                "Content-Type": ["text/html"],
                "Expires": ["Sun, 21 Jul 2024 16:10:44 GMT"],
                "Server": ["Caddy", "nginx/1.27.0"],
                "Alt-Svc": ['h3=":443"; ma=2592000'],
                "Cache-Control": ["no-cache"],
                "Date": ["Sun, 21 Jul 2024 16:10:45 GMT"],
            },
        },
        {
            "level": "info",
            "ts": 1721578227.3117847,
            "logger": "http.log.access",
            "msg": "handled request",
            "request": {
                "remote_ip": "10.0.0.2",
                "remote_port": "47142",
                "client_ip": "10.0.0.2",
                "proto": "HTTP/1.1",
                "method": "POST",
                "host": "nginx-demo.zaneops.local",
                "uri": "/docs/",
                "headers": {
                    "Content-Length": ["0"],
                    "User-Agent": ["HTTPie"],
                    "Connection": ["close"],
                },
            },
            "bytes_read": 0,
            "user_id": "",
            "duration": 0.006406094,
            "size": 157,
            "status": 405,
            "resp_headers": {
                "Server": ["Caddy", "nginx/1.27.0"],
                "Alt-Svc": ['h3=":443"; ma=2592000'],
                "Date": ["Sun, 21 Jul 2024 16:10:27 GMT"],
                "Content-Type": ["text/html"],
            },
        },
        {
            "level": "info",
            "ts": 1721578160.8126135,
            "logger": "http.log.access",
            "msg": "handled request",
            "request": {
                "remote_ip": "10.0.0.2",
                "remote_port": "33632",
                "client_ip": "10.0.0.2",
                "proto": "HTTP/1.1",
                "method": "GET",
                "host": "nginx-demo.zaneops.local",
                "uri": "/docs",
                "headers": {
                    "User-Agent": [
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:128.0) Gecko/20100101 Firefox/128.0"
                    ],
                    "Accept": [
                        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/png,image/svg+xml,*/*;q=0.8"
                    ],
                    "Dnt": ["1"],
                    "Connection": ["keep-alive"],
                    "Accept-Language": ["en,en-US;q=0.8,fr;q=0.5,fr-FR;q=0.3"],
                    "Accept-Encoding": ["gzip, deflate"],
                    "Cookie": ["REDACTED"],
                    "Upgrade-Insecure-Requests": ["1"],
                    "Sec-Gpc": ["1"],
                    "Priority": ["u=0, i"],
                },
            },
            "bytes_read": 0,
            "user_id": "",
            "duration": 0.010405301,
            "size": 12113,
            "status": 200,
            "resp_headers": {
                "Date": ["Sun, 21 Jul 2024 16:09:20 GMT"],
                "Content-Type": ["text/html"],
                "Server": ["Caddy", "nginx/1.27.0"],
                "Alt-Svc": ['h3=":443"; ma=2592000'],
                "Expires": ["Sun, 21 Jul 2024 16:09:19 GMT"],
                "Cache-Control": ["no-cache"],
            },
        },
        {
            "level": "info",
            "ts": 1721578161.903769,
            "logger": "http.log.access",
            "msg": "handled request",
            "request": {
                "remote_ip": "10.0.0.2",
                "remote_port": "33632",
                "client_ip": "10.0.0.2",
                "proto": "HTTP/1.1",
                "method": "GET",
                "host": "nginx-demo.zaneops.local",
                "uri": "/docs",
                "headers": {
                    "Accept-Encoding": ["gzip, deflate"],
                    "Connection": ["keep-alive"],
                    "Priority": ["u=0, i"],
                    "User-Agent": [
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:128.0) Gecko/20100101 Firefox/128.0"
                    ],
                    "Accept": [
                        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/png,image/svg+xml,*/*;q=0.8"
                    ],
                    "Upgrade-Insecure-Requests": ["1"],
                    "Sec-Gpc": ["1"],
                    "Accept-Language": ["en,en-US;q=0.8,fr;q=0.5,fr-FR;q=0.3"],
                    "Dnt": ["1"],
                    "Cookie": ["REDACTED"],
                },
            },
            "bytes_read": 0,
            "user_id": "",
            "duration": 0.001357747,
            "size": 12113,
            "status": 200,
            "resp_headers": {
                "Expires": ["Sun, 21 Jul 2024 16:09:20 GMT"],
                "Cache-Control": ["no-cache"],
                "Date": ["Sun, 21 Jul 2024 16:09:21 GMT"],
                "Server": ["Caddy", "nginx/1.27.0"],
                "Alt-Svc": ['h3=":443"; ma=2592000'],
                "Content-Type": ["text/html"],
            },
        },
        {
            "level": "info",
            "ts": 1721578015.8651662,
            "logger": "http.log.access",
            "msg": "handled request",
            "request": {
                "remote_ip": "10.0.0.2",
                "remote_port": "53524",
                "client_ip": "10.0.0.2",
                "proto": "HTTP/1.1",
                "method": "GET",
                "host": "nginx-demo.zaneops.local",
                "uri": "/docs",
                "headers": {
                    "Upgrade-Insecure-Requests": ["1"],
                    "Accept-Language": ["en,en-US;q=0.8,fr;q=0.5,fr-FR;q=0.3"],
                    "Accept-Encoding": ["gzip, deflate"],
                    "Connection": ["keep-alive"],
                    "Cookie": ["REDACTED"],
                    "User-Agent": [
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:128.0) Gecko/20100101 Firefox/128.0"
                    ],
                    "Accept": [
                        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/png,image/svg+xml,*/*;q=0.8"
                    ],
                    "Dnt": ["1"],
                    "Sec-Gpc": ["1"],
                    "Priority": ["u=0, i"],
                },
            },
            "bytes_read": 0,
            "user_id": "",
            "duration": 0.007462656,
            "size": 12113,
            "status": 200,
            "resp_headers": {
                "Date": ["Sun, 21 Jul 2024 16:06:55 GMT"],
                "Content-Type": ["text/html"],
                "Server": ["Caddy", "nginx/1.27.0"],
                "Alt-Svc": ['h3=":443"; ma=2592000'],
                "Expires": ["Sun, 21 Jul 2024 16:06:54 GMT"],
                "Cache-Control": ["no-cache"],
            },
        },
        {
            "level": "info",
            "ts": 1721612466.7106614,
            "logger": "http.log.access",
            "msg": "handled request",
            "request": {
                "remote_ip": "10.0.0.2",
                "remote_port": "57224",
                "client_ip": "10.0.0.2",
                "proto": "HTTP/1.1",
                "method": "GET",
                "host": "nginx-demo.zaneops.local",
                "uri": "/docs?query",
                "headers": {
                    "Cookie": ["REDACTED"],
                    "Upgrade-Insecure-Requests": ["1"],
                    "Dnt": ["1"],
                    "Connection": ["keep-alive"],
                    "Sec-Gpc": ["1"],
                    "User-Agent": [
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:128.0) Gecko/20100101 Firefox/128.0"
                    ],
                    "Accept": [
                        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/png,image/svg+xml,*/*;q=0.8"
                    ],
                    "Accept-Language": ["en,en-US;q=0.8,fr;q=0.5,fr-FR;q=0.3"],
                    "Accept-Encoding": ["gzip, deflate"],
                    "Priority": ["u=0, i"],
                },
            },
            "bytes_read": 0,
            "user_id": "",
            "duration": 0.009803894,
            "size": 12123,
            "status": 200,
            "resp_headers": {
                "Server": ["Caddy", "nginx/1.27.0"],
                "Alt-Svc": ['h3=":443"; ma=2592000'],
                "Content-Type": ["text/html"],
                "Expires": ["Mon, 22 Jul 2024 01:41:05 GMT"],
                "Cache-Control": ["no-cache"],
                "Date": ["Mon, 22 Jul 2024 01:41:06 GMT"],
            },
        },
    ]

    def test_collect_service_http_logs(self):
        p, service = self.create_and_deploy_caddy_docker_service()

        fist_deployment: DockerDeployment = service.deployments.first()

        simple_proxy_logs = [
            {
                "source": "stdout",
                "container_id": "8320676fc77bb91b54f0dff7015c08148fd3021db7038c8d0c18ec7378e1979e",
                "log": json.dumps(
                    {
                        **log,
                        "zane_deployment_upstream": f"{fist_deployment.network_aliases[-1]}:80",
                        "zane_deployment_green_hash": None,
                        "zane_deployment_blue_hash": fist_deployment.hash,
                        "zane_service_id": service.id,
                        "uuid": str(uuid.uuid4()),
                    }
                ),
                "container_name": "/zane_proxy.1.kj2d879vqbnpishh4d66i47do",
                "time": "2024-06-25T14:16:25+0000",
                "service": "proxy",
                "tag": json.dumps({"service_id": "zane.proxy"}),
            }
            for log in self.sample_log_entries
        ]

        response = self.client.post(
            reverse("zane_api:logs.ingest"),
            data=simple_proxy_logs,
            headers={
                "Authorization": f"Basic {base64.b64encode(f'zaneops:{settings.SECRET_KEY}'.encode()).decode()}"
            },
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(0, SimpleLog.objects.count())
        self.assertEqual(len(self.sample_log_entries), HttpLog.objects.count())

        log: HttpLog = HttpLog.objects.first()
        self.assertEqual(service.id, log.service_id)
        self.assertEqual(fist_deployment.hash, log.deployment_id)
        self.assertEqual(HttpLog.RequestMethod.GET, log.request_method)
        self.assertEqual(200, log.status)
        duration_nano_seconds = int(
            self.sample_log_entries[0]["duration"] * 1_000_000_000
        )
        self.assertEqual(duration_nano_seconds, log.request_duration_ns)
        self.assertEqual("/docs", log.request_path)
        self.assertEqual("query", log.request_query)
        self.assertEqual("10.0.0.2", log.request_ip)
        self.assertEqual("nginx-demo.zaneops.local", log.request_host)
        self.assertEqual(HttpLog.RequestProtocols.HTTP_2, log.request_protocol)
        self.assertIsNotNone(log.request_id)

    async def test_correctly_split_logs_per_deployment(self):
        p, service = await self.acreate_and_deploy_caddy_docker_service()
        # Make a second deployment
        await self.async_client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": service.slug,
                },
            )
        )

        latest_deployment: DockerDeployment = await service.deployments.afirst()
        initial_deployment: DockerDeployment = await service.deployments.alast()

        # First deployment logs
        first_deploy_proxy_logs = [
            {
                "source": "stdout",
                "container_id": "8320676fc77bb91b54f0dff7015c08148fd3021db7038c8d0c18ec7378e1979e",
                "log": json.dumps(
                    {
                        **log,
                        "zane_deployment_upstream": f"{initial_deployment.network_aliases[-1]}:80",
                        "zane_deployment_green_hash": "",
                        "zane_deployment_blue_hash": initial_deployment.hash,
                        "zane_service_id": service.id,
                        "uuid": str(uuid.uuid4()),
                    }
                ),
                "container_name": "/zane_proxy.1.kj2d879vqbnpishh4d66i47do",
                "time": "2024-06-25T14:16:25+0000",
                "service": "proxy",
                "tag": json.dumps({"service_id": "zane.proxy"}),
            }
            for log in self.sample_log_entries[:3]
        ]

        first_deploy_proxy_logs.append(
            {
                "source": "stdout",
                "container_id": "8320676fc77bb91b54f0dff7015c08148fd3021db7038c8d0c18ec7378e1979e",
                "log": json.dumps(
                    {
                        **self.sample_log_entries[3],
                        "zane_deployment_upstream": f"{initial_deployment.network_aliases[-1]}:80",
                        "zane_deployment_green_hash": latest_deployment.hash,
                        "zane_deployment_blue_hash": initial_deployment.hash,
                        "zane_service_id": service.id,
                        "uuid": str(uuid.uuid4()),
                    }
                ),
                "container_name": "/zane_proxy.1.kj2d879vqbnpishh4d66i47do",
                "time": "2024-06-25T14:16:25+0000",
                "service": "proxy",
                "tag": json.dumps({"service_id": "zane.proxy"}),
            }
        )

        # Second deployment logs
        second_deploy_proxy_logs = [
            {
                "source": "stdout",
                "container_id": "8320676fc77bb91b54f0dff7015c08148fd3021db7038c8d0c18ec7378e1979e",
                "log": json.dumps(
                    {
                        **log,
                        "zane_deployment_upstream": f"{latest_deployment.network_aliases[-1]}:80",
                        "zane_deployment_green_hash": latest_deployment.hash,
                        "zane_deployment_blue_hash": initial_deployment.hash,
                        "zane_service_id": service.id,
                        "uuid": str(uuid.uuid4()),
                    }
                ),
                "container_name": "/zane_proxy.1.kj2d879vqbnpishh4d66i47do",
                "time": "2024-06-25T14:16:25+0000",
                "service": "proxy",
                "tag": json.dumps({"service_id": "zane.proxy"}),
            }
            for log in self.sample_log_entries[4:]
        ]

        response = await self.async_client.post(
            reverse("zane_api:logs.ingest"),
            headers={
                "Authorization": f"Basic {base64.b64encode(f'zaneops:{settings.SECRET_KEY}'.encode()).decode()}"
            },
            data=first_deploy_proxy_logs + second_deploy_proxy_logs,
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(len(self.sample_log_entries), await HttpLog.objects.acount())

        self.assertEqual(4, await initial_deployment.http_logs.acount())
        self.assertEqual(2, await latest_deployment.http_logs.acount())


class DeploymentSystemLogViewTests(AuthAPITestCase):
    async def test_log_intermediate_steps_when_deploying_a_service(self):
        _, service = await self.acreate_and_deploy_caddy_docker_service()

        first_deployment: DockerDeployment = await service.deployments.afirst()
        self.assertNotEqual(
            0,
            await SimpleLog.objects.filter(
                source=SimpleLog.LogSource.SYSTEM,
                deployment_id=first_deployment.hash,
                service_id=service.id,
                level=SimpleLog.LogLevel.INFO,
            ).acount(),
        )
