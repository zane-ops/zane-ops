import requests


class UnknownZaneProxyError(Exception):
    pass


def register_zaneops_app_on_proxy(
    proxy_url: str,
    zane_app_domain: str,
    zane_api_internal_domain: str,
    zane_front_internal_domain: str,
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

        print(
            f"[{config_id}] Got Response from proxy :\n {response.status_code=}\n {response.text=}\n"
        )
    return
