import requests


class UnknownZaneProxyError(Exception):
    pass


def register_zaneops_app_on_proxy(
    proxy_url: str,
    zane_app_domain: str,
    zane_api_internal_domain: str,
    zane_front_internal_domain: str,
):
    response = requests.get(f"{proxy_url}/id/zaneops.internal", timeout=5)
    if response.status_code != 404 and response.status_code != 200:
        raise UnknownZaneProxyError(
            "An unknown error occurred while requesting the proxy.\n"
            + f"status code: {response.status_code}\n"
            + f"content: {response.text}"
        )

    zane_url_config = {
        "@id": "zaneops.internal",
        "handle": [
            {
                "handler": "subroute",
                "routes": [
                    {
                        "@id": f"{zane_app_domain}-api",
                        "handle": [
                            {
                                "handler": "subroute",
                                "routes": [
                                    {
                                        "handle": [
                                            {
                                                "handler": "reverse_proxy",
                                                "upstreams": [
                                                    {"dial": zane_api_internal_domain}
                                                ],
                                            }
                                        ]
                                    }
                                ],
                            }
                        ],
                        "match": [{"path": ["/api/*"]}],
                    },
                    {
                        "@id": f"{zane_app_domain}-front",
                        "handle": [
                            {
                                "handler": "subroute",
                                "routes": [
                                    {
                                        "handle": [
                                            {
                                                "handler": "reverse_proxy",
                                                "upstreams": [
                                                    {"dial": zane_front_internal_domain}
                                                ],
                                            }
                                        ]
                                    }
                                ],
                            }
                        ],
                    },
                ],
            }
        ],
        "match": [{"host": [zane_app_domain]}],
        "terminal": True,
    }

    if response.status_code == 404:
        response = requests.put(
            f"{proxy_url}/id/zane-url-root/routes/0", json=zane_url_config, timeout=5
        )
    else:
        response = requests.patch(
            f"{proxy_url}/id/zaneops.internal", timeout=5, json=zane_url_config
        )

    print(f"Got Response from proxy :\n {response.status_code=}\n {response.text=}\n")
    return
