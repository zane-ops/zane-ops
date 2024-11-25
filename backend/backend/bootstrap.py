import requests


class UnknownZaneProxyError(Exception):
    pass


def register_zaneops_app_on_proxy(
    proxy_url: str,
    zane_app_domain: str,
    zane_api_internal_domain: str,
    zane_front_internal_domain: str,
    internal_tls: bool = False,
):
    url_configurations = [
        {
            "@id": f"front.zaneops.internal",
            "group": "zaneops.internal",
            "handle": [
                {
                    "handler": "subroute",
                    "routes": [
                        {
                            "handle": [
                                {
                                    "handler": "reverse_proxy",
                                    "upstreams": [{"dial": zane_front_internal_domain}],
                                }
                            ]
                        }
                    ],
                }
            ],
            "match": [{"path": ["/*"], "host": [zane_app_domain]}],
        },
        {
            "@id": f"api.zaneops.internal",
            "group": "zaneops.internal",
            "handle": [
                {
                    "handler": "subroute",
                    "routes": [
                        {
                            "handle": [
                                {
                                    "handler": "reverse_proxy",
                                    "upstreams": [{"dial": zane_api_internal_domain}],
                                }
                            ]
                        }
                    ],
                }
            ],
            "match": [{"path": ["/api/*"], "host": [zane_app_domain]}],
        },
    ]

    for config in url_configurations:
        config_id = config["@id"]
        response = requests.get(f"{proxy_url}/id/{config_id}", timeout=5)
        if response.status_code not in [200, 404]:
            raise UnknownZaneProxyError(
                "An unknown error occurred while requesting the proxy.\n"
                + f"status code: {response.status_code}\n"
                + f"content: {response.text}"
            )

        if response.status_code == 404:
            response = requests.put(
                f"{proxy_url}/id/zane-url-root/routes/0", json=config, timeout=5
            )
        else:
            response = requests.patch(
                f"{proxy_url}/id/{config_id}", timeout=5, json=config
            )

        if 200 <= response.status_code < 300:
            print(
                f"[{Colors.BLUE}{config_id}{Colors.ENDC}] Updated proxy configuration succesfully ✅\n"
            )
        else:
            print(
                f"[{Colors.RED}{config_id}{Colors.ENDC}] ❌ Got an error when trying to update the proxy ❌"
            )
            print(f"With status code : {Colors.RED}{response.status_code}{Colors.ENDC}")
            print(f"With response data : {Colors.ORANGE}{response.text}{Colors.ENDC}\n")

    tls_app_config = {
        "automation": {
            "policies": [{"on_demand": True}],
            "on_demand": {
                "permission": {
                    "@id": "tls-endpoint",
                    "endpoint": f"http://{zane_api_internal_domain}/api/_proxy/check-certiticates",
                    "module": "http",
                }
            },
        }
    }

    if internal_tls:
        tls_app_config["automation"]["policies"][0].update(
            {"issuers": [{"module": "internal"}]}
        )
    response = requests.patch(
        f"{proxy_url}/id/root/apps/tls", timeout=5, json=tls_app_config
    )
    if 200 <= response.status_code < 300:
        print(
            f"[{Colors.BLUE}root.apps.tls{Colors.ENDC}] Updated proxy configuration succesfully ✅\n"
        )
    else:
        print(
            f"[{Colors.RED}root.apps.tls{Colors.ENDC}] ❌ Got an error when trying to update the proxy ❌"
        )
        print(f"With status code : {Colors.RED}{response.status_code}{Colors.ENDC}")
        print(f"With response data : {Colors.ORANGE}{response.text}{Colors.ENDC}\n")

    return


class Colors:
    GREEN = "\033[92m"
    BLUE = "\033[94m"
    ORANGE = "\033[38;5;208m"
    RED = "\033[91m"
    GREY = "\033[90m"
    ENDC = "\033[0m"  # Reset to default color
