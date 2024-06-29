from django.urls import reverse
from rest_framework import status

from .base import APITestCase
from ..utils import jprint


class HTTPLogCollectViewTests(APITestCase):
    def test_collect_proxy_source_logs(self):
        simple_proxy_logs = [
            {
                "source": "stdout",
                "log": '{"level":"info","ts":1719324985.9711,"logger":"http.log.access","msg":"handled request","request":{"remote_ip":"10.0.0.2","remote_port":"37420","client_ip":"10.0.0.2","proto":"HTTP/2.0","method":"GET","host":"app.zaneops.local","uri":"/api/projects/?slug=&page=1&per_page=10&sort_by=-updated_at&status=active","headers":{"Cookie":["REDACTED"],"Te":["trailers"],"Sec-Fetch-Site":["same-origin"],"Priority":["u=4"],"User-Agent":["Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:127.0) Gecko/20100101 Firefox/127.0"],"Accept":["*/*"],"Accept-Language":["en,en-US;q=0.8,fr;q=0.5,fr-FR;q=0.3"],"Dnt":["1"],"Accept-Encoding":["gzip, deflate, br, zstd"],"Referer":["https://app.zaneops.local/?slug=&page=1&per_page=10"],"Sec-Fetch-Dest":["empty"],"Content-Type":["application/json"],"Sec-Fetch-Mode":["cors"],"Sec-Gpc":["1"]},"tls":{"resumed":false,"version":772,"cipher_suite":4865,"proto":"h2","server_name":"app.zaneops.local"}},"bytes_read":0,"user_id":"","duration":0.041519349,"size":238,"status":200,"resp_headers":{"Alt-Svc":["h3=\\":443\\"; ma=2592000"],"Allow":["GET, POST, HEAD, OPTIONS"],"X-Frame-Options":["DENY"],"Vary":["Accept, Cookie"],"Server":["Caddy","WSGIServer/0.2 CPython/3.11.7"],"Content-Type":["application/json"],"Cross-Origin-Opener-Policy":["same-origin"],"Content-Length":["238"],"X-Content-Type-Options":["nosniff"],"Referrer-Policy":["same-origin"],"Date":["Tue, 25 Jun 2024 14:16:25 GMT"]}}',
                "container_id": "8320676fc77bb91b54f0dff7015c08148fd3021db7038c8d0c18ec7378e1979e",
                "container_name": "/zane_zane-proxy.1.kj2d879vqbnpishh4d66i47do",
                "time": "2024-06-25T14:16:25+0000",
                "service": "proxy",
                "tag": "zane.proxy",
            }
        ]

        response = self.client.post(
            reverse("zane_api:logs.tail"), data=simple_proxy_logs
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        jprint(response.json())
