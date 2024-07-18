import datetime
import json

from django.urls import reverse
from rest_framework import status

from .base import AuthAPITestCase
from ..models import SimpleLog, DockerDeployment, DockerRegistryService


class SimpleLogCollectViewTests(AuthAPITestCase):
    def test_collect_proxy_source_logs(self):
        simple_proxy_logs = [
            {
                "source": "stdout",
                "log": '{"level":"info","ts":1719324985.9711,"logger":"http.log.access","msg":"handled request","request":{"remote_ip":"10.0.0.2","remote_port":"37420","client_ip":"10.0.0.2","proto":"HTTP/2.0","method":"GET","host":"app.zaneops.local","uri":"/api/projects/?slug=&page=1&per_page=10&sort_by=-updated_at&status=active","headers":{"Cookie":["REDACTED"],"Te":["trailers"],"Sec-Fetch-Site":["same-origin"],"Priority":["u=4"],"User-Agent":["Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:127.0) Gecko/20100101 Firefox/127.0"],"Accept":["*/*"],"Accept-Language":["en,en-US;q=0.8,fr;q=0.5,fr-FR;q=0.3"],"Dnt":["1"],"Accept-Encoding":["gzip, deflate, br, zstd"],"Referer":["https://app.zaneops.local/?slug=&page=1&per_page=10"],"Sec-Fetch-Dest":["empty"],"Content-Type":["application/json"],"Sec-Fetch-Mode":["cors"],"Sec-Gpc":["1"]},"tls":{"resumed":false,"version":772,"cipher_suite":4865,"proto":"h2","server_name":"app.zaneops.local"}},"bytes_read":0,"user_id":"","duration":0.041519349,"size":238,"status":200,"resp_headers":{"Alt-Svc":["h3=\\":443\\"; ma=2592000"],"Allow":["GET, POST, HEAD, OPTIONS"],"X-Frame-Options":["DENY"],"Vary":["Accept, Cookie"],"Server":["Caddy","WSGIServer/0.2 CPython/3.11.7"],"Content-Type":["application/json"],"Cross-Origin-Opener-Policy":["same-origin"],"Content-Length":["238"],"X-Content-Type-Options":["nosniff"],"Referrer-Policy":["same-origin"],"Date":["Tue, 25 Jun 2024 14:16:25 GMT"]}}',
                "container_id": "8320676fc77bb91b54f0dff7015c08148fd3021db7038c8d0c18ec7378e1979e",
                "container_name": "/zane_proxy.1.kj2d879vqbnpishh4d66i47do",
                "time": "2024-06-25T14:16:25+0000",
                "service": "proxy",
                "tag": json.dumps({"service_id": "zane.proxy"}),
            }
        ]
        json_log = json.loads(simple_proxy_logs[0]["log"])

        response = self.client.post(
            reverse("zane_api:logs.tail"), data=simple_proxy_logs
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        self.assertEqual(1, SimpleLog.objects.count())
        log: SimpleLog = SimpleLog.objects.first()
        self.assertEqual(SimpleLog.LogSource.PROXY, log.source)
        self.assertEqual(SimpleLog.LogLevel.INFO, log.level)
        self.assertIsNotNone(log.time)
        self.assertEqual(json_log, log.content)

    def test_collect_service_logs(self):
        p, service = self.create_and_deploy_redis_docker_service()

        deployment: DockerDeployment = service.deployments.first()

        simple_logs = [
            {
                "log": "1:C 30 Jun 2024 03:17:14.369 * oO0OoO0OoO0Oo Redis is starting oO0OoO0OoO0Oo",
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

        response = self.client.post(reverse("zane_api:logs.tail"), data=simple_logs)
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        self.assertEqual(len(simple_logs), deployment.logs.count())
        log: SimpleLog = deployment.logs.first()
        self.assertEqual(SimpleLog.LogSource.SERVICE, log.source)
        self.assertEqual(SimpleLog.LogLevel.INFO, log.level)
        self.assertIsNotNone(log.time)
        self.assertEqual(
            "1:C 30 Jun 2024 03:17:14.369 * oO0OoO0OoO0Oo Redis is starting oO0OoO0OoO0Oo",
            log.content,
        )
        self.assertIsNotNone(log.service_id)


class LogStreamViewTests(AuthAPITestCase):
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
            datetime.datetime(2024, 6, 30, 21, 52, 22, tzinfo=datetime.timezone.utc),
            '10.0.8.103 - - [30/Jun/2024:21:52:22 +0000] "POST / HTTP/1.1" 200 12127 "-" "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:127.0) Gecko/20100101 Firefox/127.0" "10.0.0.2"',
        ),
    ]

    def test_view_logs(self):
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
                    level=(
                        SimpleLog.LogLevel.INFO
                        if i % 2 == 0
                        else SimpleLog.LogLevel.ERROR
                    ),
                )
                for i, (time, content) in enumerate(self.sample_log_contents)
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
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(len(simple_logs), len(response.json()["results"]))

    def test_paginate(self):
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
                    level=(
                        SimpleLog.LogLevel.INFO
                        if i % 2 == 0
                        else SimpleLog.LogLevel.ERROR
                    ),
                )
                for i, (time, content) in enumerate(self.sample_log_contents)
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
            QUERY_STRING="per_page=5",
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        data = response.json()
        self.assertIsNotNone(data["next"])
        self.assertEqual(5, len(data["results"]))

    def test_complex_filter(self):
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
                    level=(
                        SimpleLog.LogLevel.INFO
                        if i % 2 == 0
                        else SimpleLog.LogLevel.ERROR
                    ),
                )
                for i, (time, content) in enumerate(self.sample_log_contents)
            ]
        )

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

    def test_delete_logs_after_archiving_a_service(self):
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
                    level=SimpleLog.LogLevel.INFO,
                )
                for (time, content) in self.sample_log_contents
            ]
        )

        response = self.client.delete(
            reverse(
                "zane_api:services.docker.archive",
                kwargs={"project_slug": p.slug, "service_slug": service.slug},
            ),
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)
        deleted_service = DockerRegistryService.objects.filter(
            slug=service.slug
        ).first()
        self.assertIsNone(deleted_service)

        logs_for_service = SimpleLog.objects.filter(service_id=service.id).count()
        self.assertEqual(0, logs_for_service)
