# type: ignore
import base64
import datetime
import json
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.test import override_settings
from django.urls import reverse
from rest_framework import status

from search.dtos import RuntimeLogLevel, RuntimeLogSource
from temporal.proxy import ZaneProxyClient
from zane_api.models import Deployment, HttpLog
from zane_api.tests.base import AuthAPITestCase
from zane_api.utils import jprint
from zane_api.views.helpers import ZaneServices


def caddy_access_log(
    host: str = "nginx-demo.zaneops.local",
    uri: str = "/docs?query",
    method: str = "GET",
    status_code: int = 200,
    forwarded_for: str = "88.99.73.23",
):
    return {
        "level": "info",
        "ts": datetime.datetime.now().timestamp(),
        "logger": "http.log.access",
        "msg": "handled request",
        "request": {
            "remote_ip": "10.0.0.2",
            "remote_port": "33632",
            "client_ip": "10.0.0.2",
            "proto": "HTTP/1.1",
            "method": method,
            "host": host,
            "uri": uri,
            "headers": {
                "X-Forwarded-For": [forwarded_for],
                "User-Agent": ["HTTPie"],
                "Connection": ["keep-alive"],
            },
        },
        "bytes_read": 0,
        "user_id": "",
        "duration": 0.006841144,
        "size": 12119,
        "status": status_code,
        "resp_headers": {
            "Content-Type": ["text/html"],
            "Server": ["Caddy"],
        },
    }


def fluentd_proxy_entry(content: dict | str, source: str = "stdout"):
    return {
        "source": source,
        "container_id": "8320676fc77bb91b54f0dff7015c08148fd3021db7038c8d0c18ec7378e1979e",
        "log": content if isinstance(content, str) else json.dumps(content),
        "container_name": "/zane_proxy.1.kj2d879vqbnpishh4d66i47do",
        "time": datetime.datetime.now().isoformat(),
        "service": "proxy",
        "tag": json.dumps({"service_id": ZaneServices.PROXY}),
    }


class FakeGeoIPCountry:
    class _Country:
        def __init__(self, iso_code: str | None):
            self.iso_code = iso_code

    def __init__(self, iso_code: str | None):
        self.country = self._Country(iso_code)


class FakeGeoIPReader:
    """
    Stands in for `geoip2.database.Reader`, `ip_to_country` maps an IP to a country code,
    any unknown IP raises `AddressNotFoundError` like the real reader does.
    """

    ip_to_country = {
        "88.99.73.23": "DE",
        "2001:0db8:0000:0000:0000:ff00:0042:8329": "FR",
    }

    def __init__(self, *args, **kwargs):
        pass

    def country(self, ip: str):
        from geoip2.errors import AddressNotFoundError

        code = self.ip_to_country.get(ip)
        if code is None:
            raise AddressNotFoundError(f"{ip} not found in database")
        return FakeGeoIPCountry(code)

    def close(self):
        pass


class ProxyLogTestBase(AuthAPITestCase):
    def ingest(self, entries: list[dict]):
        response = self.client.post(
            reverse("zane_api:logs.ingest"),
            data=entries,
            headers={
                "Authorization": f"Basic {base64.b64encode(f'zaneops:{settings.SECRET_KEY}'.encode()).decode()}"
            },
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        return response

    def loginAsSimpleUser(self):
        User.objects.create_user(username="mohai", password="password")
        self.client.login(username="mohai", password="password")


class ProxyHttpLogIngestViewTests(ProxyLogTestBase):
    def test_ingest_tags_service_http_logs_with_service_source(self):
        _, service = self.create_and_deploy_caddy_docker_service()
        deployment: Deployment = service.deployments.first()

        self.ingest(
            [
                fluentd_proxy_entry(
                    {
                        **caddy_access_log(),
                        "zane_service_type": ZaneProxyClient.ServiceType.MANAGED_SERVICE,
                        "zane_deployment_upstream": f"{deployment.network_aliases[-1]}:80",
                        "zane_deployment_green_hash": None,
                        "zane_deployment_blue_hash": deployment.hash,
                        "zane_service_id": service.id,
                        "zane_deployment_id": deployment.hash,
                        "uuid": str(uuid.uuid4()),
                    }
                )
            ]
        )

        log: HttpLog = HttpLog.objects.get(service_id=service.id)
        self.assertEqual(HttpLog.LogSource.SERVICE, log.source)

    def test_ingest_zaneops_api_http_logs(self):
        """
        Requests going to the ZaneOps dashboard & API are tagged by the proxy with
        `zane_service_type=zaneops`, they used to be dropped at ingest.
        """
        self.loginUser()

        self.ingest(
            [
                fluentd_proxy_entry(
                    {
                        **caddy_access_log(
                            host=settings.ZANE_APP_DOMAIN, uri="/api/projects/"
                        ),
                        "zane_service_type": ZaneProxyClient.ServiceType.ZANE_OPS,
                        "uuid": str(uuid.uuid4()),
                    }
                )
            ]
        )

        self.assertEqual(1, HttpLog.objects.count())
        log: HttpLog = HttpLog.objects.first()
        self.assertEqual(HttpLog.LogSource.ZANE_OPS_API, log.source)
        self.assertIsNone(log.service_id)
        self.assertIsNone(log.deployment_id)
        self.assertIsNone(log.stack_id)
        self.assertEqual(settings.ZANE_APP_DOMAIN, log.request_host)
        self.assertEqual("/api/projects/", log.request_path)

    def test_ingest_zaneops_frontend_http_logs(self):
        """
        Requests to the dashboard itself are stored under the same source as the API,
        `request_path` is enough to tell them apart.
        """
        self.loginUser()

        self.ingest(
            [
                fluentd_proxy_entry(
                    {
                        **caddy_access_log(
                            host=settings.ZANE_APP_DOMAIN, uri="/project/zaneops"
                        ),
                        "zane_service_type": ZaneProxyClient.ServiceType.ZANE_OPS,
                        "uuid": str(uuid.uuid4()),
                    }
                )
            ]
        )

        self.assertEqual(1, HttpLog.objects.count())
        log: HttpLog = HttpLog.objects.first()
        self.assertEqual(HttpLog.LogSource.ZANE_OPS_FRONTEND, log.source)
        self.assertEqual("/project/zaneops", log.request_path)

    def test_ingest_drops_zaneops_static_assets_http_logs(self):
        """
        One dashboard page load pulls a dozen hashed bundles,
        storing them would drown the real traffic.
        """
        self.loginUser()

        self.ingest(
            [
                fluentd_proxy_entry(
                    {
                        **caddy_access_log(host=settings.ZANE_APP_DOMAIN, uri=uri),
                        "zane_service_type": ZaneProxyClient.ServiceType.ZANE_OPS,
                        "uuid": str(uuid.uuid4()),
                    }
                )
                for uri in [
                    "/assets/root-DkS4iiZP.js",
                    "/assets/root-BhV4qFXt.css",
                    "/fonts/GeistVF.woff2",
                    "/logo/ZaneOps-SYMBOL-BLACK.svg",
                ]
            ]
        )

        self.assertEqual(0, HttpLog.objects.count())

    def test_ingest_keeps_service_static_assets_http_logs(self):
        """
        The skip list only applies to ZaneOps' own dashboard, not to deployed services.
        """
        _, service = self.create_and_deploy_caddy_docker_service()
        deployment: Deployment = service.deployments.first()

        self.ingest(
            [
                fluentd_proxy_entry(
                    {
                        **caddy_access_log(
                            host="caddy-web-server.fkiss.me",
                            uri="/assets/index-DkS4iiZP.js",
                        ),
                        "zane_service_type": ZaneProxyClient.ServiceType.MANAGED_SERVICE,
                        "zane_deployment_upstream": f"{deployment.network_aliases[-1]}:80",
                        "zane_deployment_green_hash": None,
                        "zane_deployment_blue_hash": deployment.hash,
                        "zane_service_id": service.id,
                        "zane_deployment_id": deployment.hash,
                        "uuid": str(uuid.uuid4()),
                    }
                )
            ]
        )

        self.assertEqual(1, HttpLog.objects.count())

    def test_ingest_unmatched_http_logs(self):
        """
        Requests hitting the 404 catchall (unknown domain) carry no `zane_*` marker at all.
        """
        self.loginUser()

        self.ingest(
            [
                fluentd_proxy_entry(
                    {
                        **caddy_access_log(
                            host="unknown-domain.com", uri="/", status_code=404
                        ),
                        "uuid": str(uuid.uuid4()),
                    }
                )
            ]
        )

        self.assertEqual(1, HttpLog.objects.count())
        log: HttpLog = HttpLog.objects.first()
        self.assertEqual(HttpLog.LogSource.UNKNOWN, log.source)
        self.assertEqual("unknown-domain.com", log.request_host)
        self.assertEqual(404, log.status)

    def test_ingest_ignores_non_access_logs_as_http_logs(self):
        self.loginUser()

        self.ingest(
            [
                fluentd_proxy_entry(
                    {
                        "level": "info",
                        "ts": datetime.datetime.now().timestamp(),
                        "logger": "tls.obtain",
                        "msg": "certificate obtained successfully",
                        "identifier": "web.zaneops.local",
                    },
                    source="stderr",
                )
            ]
        )

        self.assertEqual(0, HttpLog.objects.count())


# @override_settings(MAXMIND_DB_PATH="/tmp/GeoLite2-Country.mmdb")
# class ProxyHttpLogGeoIPTests(ProxyLogTestBase):
#     def setUp(self):
#         super().setUp()
#         from zane_api import geoip

#         geoip.get_geoip_reader.cache_clear()
#         self.addCleanup(geoip.get_geoip_reader.cache_clear)
#         patch("zane_api.geoip.Reader", new=FakeGeoIPReader).start()

#     def test_ingest_resolves_country_from_forwarded_ip(self):
#         self.loginUser()

#         self.ingest(
#             [
#                 fluentd_proxy_entry(
#                     {
#                         **caddy_access_log(forwarded_for="88.99.73.23"),
#                         "uuid": str(uuid.uuid4()),
#                     }
#                 )
#             ]
#         )

#         log: HttpLog = HttpLog.objects.first()
#         self.assertEqual("88.99.73.23", log.request_ip)
#         self.assertEqual("DE", log.request_country_code)

#     def test_ingest_resolves_country_for_ipv6(self):
#         self.loginUser()

#         self.ingest(
#             [
#                 fluentd_proxy_entry(
#                     {
#                         **caddy_access_log(
#                             forwarded_for="2001:0db8:0000:0000:0000:ff00:0042:8329"
#                         ),
#                         "uuid": str(uuid.uuid4()),
#                     }
#                 )
#             ]
#         )

#         log: HttpLog = HttpLog.objects.first()
#         self.assertEqual("FR", log.request_country_code)

#     def test_ingest_country_is_null_for_unknown_ip(self):
#         self.loginUser()

#         self.ingest(
#             [
#                 fluentd_proxy_entry(
#                     {
#                         **caddy_access_log(forwarded_for="192.168.1.10"),
#                         "uuid": str(uuid.uuid4()),
#                     }
#                 )
#             ]
#         )

#         log: HttpLog = HttpLog.objects.first()
#         self.assertIsNone(log.request_country_code)

#     @override_settings(MAXMIND_DB_PATH=None)
#     def test_ingest_country_is_null_when_geoip_is_not_configured(self):
#         self.loginUser()

#         self.ingest(
#             [
#                 fluentd_proxy_entry(
#                     {
#                         **caddy_access_log(forwarded_for="88.99.73.23"),
#                         "uuid": str(uuid.uuid4()),
#                     }
#                 )
#             ]
#         )

#         log: HttpLog = HttpLog.objects.first()
#         self.assertIsNone(log.request_country_code)

#     def test_geoip_country_is_exposed_in_the_api(self):
#         self.loginUser()

#         self.ingest(
#             [
#                 fluentd_proxy_entry(
#                     {
#                         **caddy_access_log(forwarded_for="88.99.73.23"),
#                         "uuid": str(uuid.uuid4()),
#                     }
#                 )
#             ]
#         )

#         response = self.client.get(reverse("console:proxy.http_logs"))
#         self.assertEqual(status.HTTP_200_OK, response.status_code)
#         self.assertEqual("DE", response.json()["results"][0]["request_country_code"])


class ProxyMasterHttpLogViewTests(ProxyLogTestBase):
    def setup_logs(self):
        _, service = self.create_and_deploy_caddy_docker_service()
        deployment: Deployment = service.deployments.first()

        self.ingest(
            [
                # a service request
                fluentd_proxy_entry(
                    {
                        **caddy_access_log(host="caddy-web-server.fkiss.me"),
                        "zane_service_type": ZaneProxyClient.ServiceType.MANAGED_SERVICE,
                        "zane_deployment_upstream": f"{deployment.network_aliases[-1]}:80",
                        "zane_deployment_green_hash": None,
                        "zane_deployment_blue_hash": deployment.hash,
                        "zane_service_id": service.id,
                        "zane_deployment_id": deployment.hash,
                        "uuid": str(uuid.uuid4()),
                    }
                ),
                # a request to zaneops itself
                fluentd_proxy_entry(
                    {
                        **caddy_access_log(
                            host=settings.ZANE_APP_DOMAIN, uri="/api/projects/"
                        ),
                        "zane_service_type": ZaneProxyClient.ServiceType.ZANE_OPS,
                        "uuid": str(uuid.uuid4()),
                    }
                ),
                # a request to an unknown domain
                fluentd_proxy_entry(
                    {
                        **caddy_access_log(
                            host="unknown-domain.com",
                            uri="/",
                            method="POST",
                            status_code=404,
                        ),
                        "uuid": str(uuid.uuid4()),
                    }
                ),
            ]
        )
        return service, deployment

    def test_list_all_http_logs_accross_services_and_zaneops(self):
        self.setup_logs()

        response = self.client.get(reverse("console:proxy.http_logs"))
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(3, len(response.json()["results"]))

    def test_filter_http_logs_by_source(self):
        self.setup_logs()

        response = self.client.get(
            reverse(
                "console:proxy.http_logs",
                query={"source": HttpLog.LogSource.ZANE_OPS},
            )
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        results = response.json()["results"]
        self.assertEqual(1, len(results))
        self.assertEqual(settings.ZANE_APP_DOMAIN, results[0]["request_host"])

    def test_filter_http_logs_by_multiple_sources(self):
        self.setup_logs()

        response = self.client.get(
            reverse(
                "console:proxy.http_logs",
                query=[
                    ("source", HttpLog.LogSource.ZANE_OPS),
                    ("source", HttpLog.LogSource.UNKNOWN),
                ],
            )
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(2, len(response.json()["results"]))

    def test_filter_http_logs_by_service_id(self):
        service, _ = self.setup_logs()

        response = self.client.get(
            reverse("console:proxy.http_logs", query={"service_id": service.id})
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(1, len(response.json()["results"]))

    def test_filter_http_logs_by_status_and_method(self):
        self.setup_logs()

        response = self.client.get(
            reverse(
                "console:proxy.http_logs",
                query={"status": "4xx", "request_method": "POST"},
            )
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        results = response.json()["results"]
        self.assertEqual(1, len(results))
        self.assertEqual("unknown-domain.com", results[0]["request_host"])

    def test_http_logs_expose_the_owning_service(self):
        service, deployment = self.setup_logs()

        response = self.client.get(
            reverse("console:proxy.http_logs", query={"service_id": service.id})
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        log = response.json()["results"][0]
        self.assertEqual(service.id, log["service_id"])
        self.assertEqual(deployment.hash, log["deployment_id"])
        self.assertEqual(HttpLog.LogSource.SERVICE, log["source"])

    def test_view_single_zaneops_http_log(self):
        self.setup_logs()

        log: HttpLog = HttpLog.objects.get(source=HttpLog.LogSource.ZANE_OPS)
        response = self.client.get(
            reverse(
                "console:proxy.http_logs.single",
                kwargs={"request_uuid": log.request_uuid},
            )
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(str(log.id), response.json()["id"])

    def test_http_logs_fields_autocomplete(self):
        self.setup_logs()

        response = self.client.get(
            reverse(
                "console:proxy.http_logs.fields",
                query={"field": "request_host", "value": ""},
            )
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(
            {
                "caddy-web-server.fkiss.me",
                settings.ZANE_APP_DOMAIN,
                "unknown-domain.com",
            },
            set(response.json()),
        )

    def test_http_logs_fields_autocomplete_with_a_value(self):
        self.setup_logs()

        response = self.client.get(
            reverse(
                "console:proxy.http_logs.fields",
                query={"field": "request_host", "value": "unknown"},
            )
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(["unknown-domain.com"], response.json())

    def test_non_instance_owner_cannot_view_master_http_logs(self):
        self.setup_logs()
        self.loginAsSimpleUser()

        response = self.client.get(reverse("console:proxy.http_logs"))
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_non_instance_owner_cannot_view_master_http_logs_fields(self):
        self.setup_logs()
        self.loginAsSimpleUser()

        response = self.client.get(
            reverse(
                "console:proxy.http_logs.fields",
                query={"field": "request_host", "value": ""},
            )
        )
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_anonymous_user_cannot_view_master_http_logs(self):
        self.setup_logs()
        self.client.logout()

        response = self.client.get(reverse("console:proxy.http_logs"))
        self.assertEqual(status.HTTP_401_UNAUTHORIZED, response.status_code)


# class ProxyApplicationLogIngestViewTests(ProxyLogTestBase):
#     def test_ingest_proxy_application_logs(self):
#         self.loginUser()

#         app_log = {
#             "level": "info",
#             "ts": datetime.datetime.now().timestamp(),
#             "logger": "tls.obtain",
#             "msg": "certificate obtained successfully",
#             "identifier": "web.zaneops.local",
#         }
#         self.ingest([fluentd_proxy_entry(app_log, source="stderr")])

#         data = self.search_client.search(
#             query={"source": [RuntimeLogSource.PROXY]},
#         )
#         self.assertEqual(1, len(data["results"]))
#         log = data["results"][0]
#         self.assertEqual(RuntimeLogSource.PROXY, log["source"])
#         self.assertEqual(RuntimeLogLevel.INFO, log["level"])
#         self.assertEqual(json.dumps(app_log), log["content"])

#     def test_ingest_proxy_application_logs_map_caddy_level_to_log_level(self):
#         self.loginUser()

#         self.ingest(
#             [
#                 fluentd_proxy_entry(
#                     {
#                         "level": "error",
#                         "ts": datetime.datetime.now().timestamp(),
#                         "logger": "tls.obtain",
#                         "msg": "could not get certificate from issuer",
#                         "identifier": "web.zaneops.local",
#                     },
#                     source="stderr",
#                 ),
#                 fluentd_proxy_entry(
#                     {
#                         "level": "warn",
#                         "ts": datetime.datetime.now().timestamp(),
#                         "logger": "tls",
#                         "msg": "storage cleaning happened too recently",
#                     },
#                     source="stderr",
#                 ),
#                 fluentd_proxy_entry(
#                     {
#                         "level": "debug",
#                         "ts": datetime.datetime.now().timestamp(),
#                         "logger": "http",
#                         "msg": "provisioning server",
#                     },
#                     source="stderr",
#                 ),
#             ]
#         )

#         errors = self.search_client.search(
#             query={
#                 "source": [RuntimeLogSource.PROXY],
#                 "level": [RuntimeLogLevel.ERROR],
#             },
#         )
#         self.assertEqual(2, len(errors["results"]))

#         infos = self.search_client.search(
#             query={
#                 "source": [RuntimeLogSource.PROXY],
#                 "level": [RuntimeLogLevel.INFO],
#             },
#         )
#         self.assertEqual(1, len(infos["results"]))

#     def test_ingest_non_json_proxy_logs(self):
#         self.loginUser()

#         self.ingest(
#             [
#                 fluentd_proxy_entry(
#                     "run: loading initial config: loading new config: http app module: start: listening on :443",
#                     source="stderr",
#                 )
#             ]
#         )

#         data = self.search_client.search(query={"source": [RuntimeLogSource.PROXY]})
#         self.assertEqual(1, len(data["results"]))
#         self.assertEqual(RuntimeLogLevel.INFO, data["results"][0]["level"])

#     def test_ingest_does_not_store_access_logs_as_application_logs(self):
#         self.loginUser()

#         self.ingest(
#             [
#                 fluentd_proxy_entry(
#                     {**caddy_access_log(), "uuid": str(uuid.uuid4())},
#                 )
#             ]
#         )

#         data = self.search_client.search(query={"source": [RuntimeLogSource.PROXY]})
#         self.assertEqual(0, len(data["results"]))
#         self.assertEqual(1, HttpLog.objects.count())


# class ProxyApplicationLogViewTests(ProxyLogTestBase):
#     def setup_logs(self):
#         self.loginUser()
#         self.ingest(
#             [
#                 fluentd_proxy_entry(
#                     {
#                         "level": "error",
#                         "ts": datetime.datetime.now().timestamp(),
#                         "logger": "tls.obtain",
#                         "msg": "could not get certificate from issuer",
#                         "identifier": "web.zaneops.local",
#                     },
#                     source="stderr",
#                 ),
#                 fluentd_proxy_entry(
#                     {
#                         "level": "info",
#                         "ts": datetime.datetime.now().timestamp(),
#                         "logger": "admin.api",
#                         "msg": "load complete",
#                     },
#                     source="stderr",
#                 ),
#             ]
#         )

#     def test_view_proxy_logs(self):
#         self.setup_logs()

#         response = self.client.get(reverse("console:proxy.logs"))
#         jprint(response.json())
#         self.assertEqual(status.HTTP_200_OK, response.status_code)
#         self.assertEqual(2, len(response.json()["results"]))

#     def test_filter_proxy_logs_by_level(self):
#         self.setup_logs()

#         response = self.client.get(
#             reverse("console:proxy.logs", query={"level": RuntimeLogLevel.ERROR})
#         )
#         self.assertEqual(status.HTTP_200_OK, response.status_code)
#         self.assertEqual(1, len(response.json()["results"]))

#     def test_search_proxy_logs_by_content(self):
#         self.setup_logs()

#         response = self.client.get(
#             reverse("console:proxy.logs", query={"query": "load complete"})
#         )
#         self.assertEqual(status.HTTP_200_OK, response.status_code)
#         self.assertEqual(1, len(response.json()["results"]))

#     def test_proxy_logs_do_not_include_service_logs(self):
#         _, service = self.create_and_deploy_redis_docker_service()
#         deployment: Deployment = service.deployments.first()

#         self.ingest(
#             [
#                 {
#                     "log": "1:M 30 Jun 2024 03:17:14.376 * Ready to accept connections tcp",
#                     "container_id": "78dfe81bb4b3994eeb38f65f5a586084a2b4a649c0ab08b614d0f4c2cb499761",
#                     "container_name": "/srv-redis.1.zm0uncmx8w4wvnokdl6qxt55e",
#                     "time": (
#                         datetime.datetime.now() - timedelta(seconds=1)
#                     ).isoformat(),
#                     "tag": json.dumps(
#                         {
#                             "deployment_id": deployment.hash,
#                             "service_id": service.id,
#                         }
#                     ),
#                     "source": "stdout",
#                 }
#             ]
#         )

#         response = self.client.get(reverse("console:proxy.logs"))
#         self.assertEqual(status.HTTP_200_OK, response.status_code)
#         self.assertEqual(0, len(response.json()["results"]))

#     def test_non_instance_owner_cannot_view_proxy_logs(self):
#         self.setup_logs()
#         self.loginAsSimpleUser()

#         response = self.client.get(reverse("console:proxy.logs"))
#         self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)
