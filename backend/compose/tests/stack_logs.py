import base64

from datetime import datetime, timedelta
import json
from typing import cast
import uuid
from django.urls import reverse


from .fixtures import DOCKER_COMPOSE_WEB_SERVICE, DOCKER_COMPOSE_MULTIPLE_WEB_SERVICES
from .stacks import ComposeStackAPITestBase
from zane_api.utils import jprint
from rest_framework import status
from django.conf import settings
from zane_api.models import HttpLog


class HTTPLogComposeStackCollectViewTests(ComposeStackAPITestBase):
    sample_log_entries = [
        {
            "level": "info",
            "ts": 1769306751.3443277,  # earliest
            "logger": "http.log.access",
            "msg": "handled request",
            "request": {
                "remote_ip": "192.168.97.1",
                "remote_port": "35902",
                "client_ip": "192.168.97.1",
                "proto": "HTTP/1.1",
                "method": "GET",
                "host": "immich.127-0-0-1.sslip.io",
                "uri": "/_app/immutable/chunks/D8I0erta.js",
                "headers": {
                    "Origin": ["http://immich.127-0-0-1.sslip.io"],
                    "Accept": ["*/*"],
                    "Accept-Encoding": ["gzip, deflate"],
                    "Accept-Language": ["en,en-US;q=0.9,fr-FR;q=0.8,fr;q=0.7"],
                    "Cookie": ["REDACTED"],
                    "Connection": ["keep-alive"],
                    "User-Agent": [
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
                    ],
                },
            },
            "bytes_read": 0,
            "user_id": "",
            "duration": 0.00776335,
            "size": 151,
            "status": 200,
            "resp_headers": {
                "X-Powered-By": ["Express"],
                "Content-Length": ["151"],
                "Date": ["Sun, 25 Jan 2026 02:05:51 GMT"],
                "Server": ["Caddy"],
                "X-Zane-Request-Id": ["05e74214-15c8-408f-a340-b30c8b41efce"],
                "Vary": ["Accept-Encoding"],
                "Content-Type": ["text/javascript"],
                "Cache-Control": ["public,max-age=31536000,immutable"],
                "Last-Modified": ["Fri, 19 Dec 2025 15:07:33 GMT"],
                "Content-Encoding": ["gzip"],
                "Etag": ['W/"151-1766156853000"'],
                "Alt-Svc": ['h3=":443"; ma=2592000'],
            },
            "zane_request_id": "05e74214-15c8-408f-a340-b30c8b41efce",
            "zane_service_type": "compose_stack_service",
        },
        {
            "level": "info",
            "ts": 1769306954.0115833,
            "logger": "http.log.access",
            "msg": "handled request",
            "request": {
                "remote_ip": "192.168.97.1",
                "remote_port": "21114",
                "client_ip": "192.168.97.1",
                "proto": "HTTP/1.1",
                "method": "POST",
                "host": "immich.127-0-0-1.sslip.io",
                "uri": "/api/assets",
                "headers": {
                    "Cookie": ["REDACTED"],
                    "Referer": [
                        "http://immich.127-0-0-1.sslip.io/photos?at=4ead7a6c-fe94-427c-b96a-364cbf9ec93a"
                    ],
                    "Accept-Encoding": ["gzip, deflate"],
                    "Connection": ["keep-alive"],
                    "Accept-Language": ["en,en-US;q=0.9,fr-FR;q=0.8,fr;q=0.7"],
                    "User-Agent": [
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
                    ],
                    "Content-Type": [
                        "multipart/form-data; boundary=----WebKitFormBoundaryoWNuJNMu6BOUzoGr"
                    ],
                    "Origin": ["http://immich.127-0-0-1.sslip.io"],
                    "Accept": ["*/*"],
                    "Content-Length": ["362910"],
                },
            },
            "bytes_read": 362910,
            "user_id": "",
            "duration": 0.165893452,
            "size": 64,
            "status": 201,
            "resp_headers": {
                "X-Zane-Request-Id": ["333113cf-e2e7-4eaa-ab27-b69e02ce26bc"],
                "X-Immich-Cid": ["7te6fh1l"],
                "Etag": ['"40-C2ZKmMY6c7zXkFyvm79hkUTLgtM"'],
                "Content-Type": ["application/json; charset=utf-8"],
                "Date": ["Sun, 25 Jan 2026 02:09:14 GMT"],
                "Server": ["Caddy"],
                "Alt-Svc": ['h3=":443"; ma=2592000'],
                "Vary": ["Accept-Encoding"],
                "X-Powered-By": ["Express"],
                "Content-Length": ["64"],
            },
            "zane_request_id": "333113cf-e2e7-4eaa-ab27-b69e02ce26bc",
            "zane_service_type": "compose_stack_service",
        },
        {
            "level": "info",
            "ts": 1769306954.1968405,
            "logger": "http.log.access",
            "msg": "handled request",
            "request": {
                "remote_ip": "192.168.97.1",
                "remote_port": "62693",
                "client_ip": "192.168.97.1",
                "proto": "HTTP/1.1",
                "method": "POST",
                "host": "immich.127-0-0-1.sslip.io",
                "uri": "/api/assets",
                "headers": {
                    "Accept-Encoding": ["gzip, deflate"],
                    "Cookie": ["REDACTED"],
                    "User-Agent": [
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
                    ],
                    "Accept": ["*/*"],
                    "Referer": [
                        "http://immich.127-0-0-1.sslip.io/photos?at=4ead7a6c-fe94-427c-b96a-364cbf9ec93a"
                    ],
                    "Connection": ["keep-alive"],
                    "Content-Length": ["342875"],
                    "Origin": ["http://immich.127-0-0-1.sslip.io"],
                    "Content-Type": [
                        "multipart/form-data; boundary=----WebKitFormBoundarylDOayJBDeYU18wDz"
                    ],
                    "Accept-Language": ["en,en-US;q=0.9,fr-FR;q=0.8,fr;q=0.7"],
                },
            },
            "bytes_read": 342875,
            "user_id": "",
            "duration": 0.083273059,
            "size": 64,
            "status": 201,
            "resp_headers": {
                "X-Immich-Cid": ["u7s744se"],
                "Etag": ['"40-hMozA5yfJ/l65iVJOgRLkjSSPb4"'],
                "Server": ["Caddy"],
                "X-Zane-Request-Id": ["21929146-1a5f-4800-8916-0ee4912efbbd"],
                "Date": ["Sun, 25 Jan 2026 02:09:14 GMT"],
                "X-Powered-By": ["Express"],
                "Alt-Svc": ['h3=":443"; ma=2592000'],
                "Content-Type": ["application/json; charset=utf-8"],
                "Content-Length": ["64"],
                "Vary": ["Accept-Encoding"],
            },
            "zane_request_id": "21929146-1a5f-4800-8916-0ee4912efbbd",
            "zane_service_type": "compose_stack_service",
        },
        {
            "level": "info",
            "ts": 1769306964.0736792,
            "logger": "http.log.access",
            "msg": "handled request",
            "request": {
                "remote_ip": "192.168.97.1",
                "remote_port": "49367",
                "client_ip": "192.168.97.1",
                "proto": "HTTP/1.1",
                "method": "GET",
                "host": "immich.127-0-0-1.sslip.io",
                "uri": "/api/assets/14d6e54b-c89a-4276-8f9d-e459e754492f/thumbnail?size=thumbnail&c=4BgGHITwjldOc3Z%2BZpbKYJYLVg%3D%3D",
                "headers": {
                    "User-Agent": [
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
                    ],
                    "Accept": [
                        "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
                    ],
                    "Referer": [
                        "http://immich.127-0-0-1.sslip.io/photos?at=4ead7a6c-fe94-427c-b96a-364cbf9ec93a"
                    ],
                    "Accept-Encoding": ["gzip, deflate"],
                    "Accept-Language": ["en,en-US;q=0.9,fr-FR;q=0.8,fr;q=0.7"],
                    "Cookie": ["REDACTED"],
                    "Connection": ["keep-alive"],
                },
            },
            "bytes_read": 0,
            "user_id": "",
            "duration": 0.080325193,
            "size": 27584,
            "status": 200,
            "resp_headers": {
                "Date": ["Sun, 25 Jan 2026 02:09:24 GMT"],
                "Server": ["Caddy"],
                "X-Zane-Request-Id": ["39213b1f-c22f-4fd3-bff3-f7f9f210dad7"],
                "X-Powered-By": ["Express"],
                "Cache-Control": ["private, max-age=86400, no-transform"],
                "Last-Modified": ["Sun, 25 Jan 2026 02:09:14 GMT"],
                "X-Immich-Cid": ["0m5p7xmd"],
                "Content-Disposition": [
                    "inline; filename*=UTF-8''2CCE327C-9D64-4899-811A-C6B2B09C6E96_1_105_c_thumbnail.webp"
                ],
                "Alt-Svc": ['h3=":443"; ma=2592000'],
                "Content-Type": ["image/webp"],
                "Etag": ['W/"6bc0-19bf2e99b5e"'],
                "Accept-Ranges": ["bytes"],
                "Content-Length": ["27584"],
            },
            "zane_request_id": "39213b1f-c22f-4fd3-bff3-f7f9f210dad7",
            "zane_service_type": "compose_stack_service",
        },
        {
            "level": "info",
            "ts": 1769307010.5890772,
            "logger": "http.log.access",
            "msg": "handled request",
            "request": {
                "remote_ip": "192.168.97.1",
                "remote_port": "54931",
                "client_ip": "192.168.97.1",
                "proto": "HTTP/1.1",
                "method": "GET",
                "host": "immich.127-0-0-1.sslip.io",
                "uri": "/api/albums?shared=true",
                "headers": {
                    "Connection": ["keep-alive"],
                    "Accept": ["application/json"],
                    "Referer": ["http://immich.127-0-0-1.sslip.io/map"],
                    "Cookie": ["REDACTED"],
                    "If-None-Match": ['"2-l9Fw4VUO7kr8CvBlt4zaMCqXZ0w"'],
                    "User-Agent": [
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
                    ],
                    "Accept-Encoding": ["gzip, deflate"],
                    "Accept-Language": ["en,en-US;q=0.9,fr-FR;q=0.8,fr;q=0.7"],
                },
            },
            "bytes_read": 0,
            "user_id": "",
            "duration": 0.050486291,
            "size": 0,
            "status": 304,
            "resp_headers": {
                "Alt-Svc": ['h3=":443"; ma=2592000'],
                "X-Zane-Request-Id": ["ac8b007b-101d-4753-b822-6acd70c90a56"],
                "X-Powered-By": ["Express"],
                "X-Immich-Cid": ["lmgpt4ib"],
                "Etag": ['"2-l9Fw4VUO7kr8CvBlt4zaMCqXZ0w"'],
                "Date": ["Sun, 25 Jan 2026 02:10:10 GMT"],
                "Vary": ["Accept-Encoding"],
                "Server": ["Caddy"],
            },
            "zane_request_id": "ac8b007b-101d-4753-b822-6acd70c90a56",
            "zane_service_type": "compose_stack_service",
        },
        {
            "level": "info",
            "ts": 1769307011.5890772,  # latest
            "logger": "http.log.access",
            "msg": "handled request",
            "request": {
                "remote_ip": "192.168.97.1",
                "remote_port": "54931",
                "client_ip": "192.168.97.1",
                "proto": "HTTP/1.1",
                "method": "GET",
                "host": "immich.127-0-0-1.sslip.io",
                "uri": "/api/albums?shared=true",
                "headers": {
                    "Connection": ["keep-alive"],
                    "Accept": ["application/json"],
                    "Referer": ["http://immich.127-0-0-1.sslip.io/map"],
                    "Cookie": ["REDACTED"],
                    "If-None-Match": ['"2-l9Fw4VUO7kr8CvBlt4zaMCqXZ0w"'],
                    "User-Agent": [
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
                    ],
                    "Accept-Encoding": ["gzip, deflate"],
                    "Accept-Language": ["en,en-US;q=0.9,fr-FR;q=0.8,fr;q=0.7"],
                },
            },
            "bytes_read": 0,
            "user_id": "",
            "duration": 0.050486291,
            "size": 0,
            "status": 304,
            "resp_headers": {
                "Alt-Svc": ['h3=":443"; ma=2592000'],
                "X-Zane-Request-Id": ["ac8b007b-101d-4753-b822-6acd70c90a56"],
                "X-Powered-By": ["Express"],
                "X-Immich-Cid": ["lmgpt4ib"],
                "Etag": ['"2-l9Fw4VUO7kr8CvBlt4zaMCqXZ0w"'],
                "Date": ["Sun, 25 Jan 2026 02:10:10 GMT"],
                "Vary": ["Accept-Encoding"],
                "Server": ["Caddy"],
            },
            "zane_request_id": "ac8b007b-101d-4753-b822-6acd70c90a56",
            "zane_service_type": "compose_stack_service",
        },
    ]

    def test_ingest_stack_httplogs(self):
        # Deploy initial stack
        project, stack = self.create_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_WEB_SERVICE
        )

        simple_proxy_logs = [
            {
                "source": "stdout",
                "container_id": "8320676fc77bb91b54f0dff7015c08148fd3021db7038c8d0c18ec7378e1979e",
                "log": json.dumps(
                    {
                        **log,
                        "zane_stack_id": stack.id,
                        "zane_stack_service_name": "web",
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

        # ingest logs
        response = self.client.post(
            reverse("zane_api:logs.ingest"),
            data=simple_proxy_logs,
            headers={
                "Authorization": f"Basic {base64.b64encode(f'zaneops:{settings.SECRET_KEY}'.encode()).decode()}"
            },
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(len(self.sample_log_entries), HttpLog.objects.count())

        log = cast(HttpLog, HttpLog.objects.latest("time"))
        self.assertEqual(stack.id, log.stack_id)
        self.assertEqual(HttpLog.RequestMethod.GET, log.request_method)
        self.assertEqual(304, log.status)
        self.assertEqual("immich.127-0-0-1.sslip.io", log.request_host)
        self.assertEqual("/api/albums", log.request_path)
        self.assertEqual("shared=true", log.request_query)
        self.assertEqual("192.168.97.1", log.request_ip)

    def test_ingest_stack_per_service_httplogs(self):
        # Deploy initial stack
        project, stack = self.create_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_MULTIPLE_WEB_SERVICES
        )

        simple_proxy_logs = [
            {
                "source": "stdout",
                "container_id": "8320676fc77bb91b54f0dff7015c08148fd3021db7038c8d0c18ec7378e1979e",
                "log": json.dumps(
                    {
                        **log,
                        "zane_stack_id": stack.id,
                        "zane_stack_service_name": "frontend"
                        if index % 2 == 0
                        else "api",
                        "uuid": str(uuid.uuid4()),
                    }
                ),
                "container_name": "/zane_proxy.1.kj2d879vqbnpishh4d66i47do",
                "time": "2024-06-25T14:16:25+0000",
                "service": "proxy",
                "tag": json.dumps({"service_id": "zane.proxy"}),
            }
            for index, log in enumerate(self.sample_log_entries)
        ]

        # ingest logs
        response = self.client.post(
            reverse("zane_api:logs.ingest"),
            data=simple_proxy_logs,
            headers={
                "Authorization": f"Basic {base64.b64encode(f'zaneops:{settings.SECRET_KEY}'.encode()).decode()}"
            },
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(len(self.sample_log_entries), HttpLog.objects.count())

        self.assertEqual(
            len(self.sample_log_entries) // 2,
            HttpLog.objects.filter(stack_service_name="frontend").count(),
        )
        self.assertEqual(
            len(self.sample_log_entries) // 2,
            HttpLog.objects.filter(stack_service_name="api").count(),
        )


now = datetime.now()


class RuntimelogComposeStackCollectViewTests(ComposeStackAPITestBase):
    sample_logs = [
        {
            "container_name": "/zn-compose_stk_mfynFkbQ_mfynfkbq_backend.1.xj5ew8avqg0n4tpksir93zjgp",
            "source": "stdout",
            "log": '\u001b[2m2026-01-25T17:12:12.857167Z\u001b[0m \u001b[32m INFO\u001b[0m \u001b[2mconvex-cloud-http\u001b[0m\u001b[2m:\u001b[0m [] 10.0.1.3:43466 "GET /api/shapes2 HTTP/1.1" 200 "http://compose-convex-1crnchiscp.127-0-0-1.sslip.io/" "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36" application/json - 0.473ms',
            "container_id": "2978edd2a498d5dc08f74217a669fc4553030e9a6b2379e3cf0cd24599d2a9e2",
            "time": (now - timedelta(seconds=5)).isoformat(),
        },
        {
            "log": '\u001b[2m2026-01-25T17:14:18.855477Z\u001b[0m \u001b[32m INFO\u001b[0m \u001b[2mconvex-cloud-http\u001b[0m\u001b[2m:\u001b[0m [] 10.0.1.3:43466 "GET /api/shapes2 HTTP/1.1" 200 "http://compose-convex-1crnchiscp.127-0-0-1.sslip.io/" "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36" application/json - 1.906ms',
            "container_id": "2978edd2a498d5dc08f74217a669fc4553030e9a6b2379e3cf0cd24599d2a9e2",
            "container_name": "/zn-compose_stk_mfynFkbQ_mfynfkbq_backend.1.xj5ew8avqg0n4tpksir93zjgp",
            "source": "stdout",
            "time": (now - timedelta(seconds=4)).isoformat(),
        },
        {
            "container_id": "2978edd2a498d5dc08f74217a669fc4553030e9a6b2379e3cf0cd24599d2a9e2",
            "container_name": "/zn-compose_stk_mfynFkbQ_mfynfkbq_backend.1.xj5ew8avqg0n4tpksir93zjgp",
            "source": "stdout",
            "log": '\u001b[2m2026-01-25T17:15:42.856911Z\u001b[0m \u001b[32m INFO\u001b[0m \u001b[2mconvex-cloud-http\u001b[0m\u001b[2m:\u001b[0m [] 10.0.1.3:43466 "GET /api/shapes2 HTTP/1.1" 200 "http://compose-convex-1crnchiscp.127-0-0-1.sslip.io/" "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36" application/json - 0.501ms',
            "time": (now - timedelta(seconds=3)).isoformat(),
        },
        {
            "source": "stdout",
            "log": "",
            "container_id": "bc603d5dd4ea387ae8f37470d487e48cbed5e05f78ab23d9f87011faa1bee2f1",
            "container_name": "/zn-compose_stk_mfynFkbQ_mfynfkbq_dashboard.1.qs985zn1t8rebn3xessh698yz",
            "time": (now - timedelta(seconds=2)).isoformat(),
        },
        {
            "container_name": "/zn-compose_stk_mfynFkbQ_mfynfkbq_dashboard.1.qs985zn1t8rebn3xessh698yz",
            "source": "stdout",
            "log": " \u2713 Starting...",
            "container_id": "bc603d5dd4ea387ae8f37470d487e48cbed5e05f78ab23d9f87011faa1bee2f1",
            "time": (now - timedelta(seconds=1)).isoformat(),
        },
        {
            "container_id": "bc603d5dd4ea387ae8f37470d487e48cbed5e05f78ab23d9f87011faa1bee2f1",
            "container_name": "/zn-compose_stk_mfynFkbQ_mfynfkbq_dashboard.1.qs985zn1t8rebn3xessh698yz",
            "source": "stdout",
            "log": " \u2713 Ready in 352ms",
            "time": now.isoformat(),
        },
    ]

    def test_ingest_stack_service_logs(self):
        # Deploy initial stack
        p, stack = self.create_and_deploy_compose_stack(
            content=DOCKER_COMPOSE_MULTIPLE_WEB_SERVICES
        )

        # Insert logs
        simple_logs = [
            {
                **content,
                "tag": json.dumps(
                    {
                        "zane.stack": stack.id,
                        "zane.stack.service": (
                            "frontend"
                            if i >= len(self.sample_logs) // 2
                            else "api"  # frontend is the last 3 logs
                        ),
                    }
                ),
                "source": "stdout" if i % 2 == 0 else "stderr",
            }
            for i, content in enumerate(self.sample_logs)
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
                "compose:stack.runtime_logs",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "slug": stack.slug,
                },
            ),
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        # check that all logs have been inserted
        self.assertEqual(len(simple_logs), len(response.json()["results"]))

        response = self.client.get(
            reverse(
                "compose:stack.runtime_logs",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "slug": stack.slug,
                },
                query={"stack_service_names": "frontend"},
            ),
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        # check that all logs for frontend
        self.assertEqual(len(simple_logs) // 2, len(response.json()["results"]))
