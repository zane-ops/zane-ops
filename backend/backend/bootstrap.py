import requests


class UnknownZaneProxyError(Exception):
    pass


DEFAULT_404_FALLBACK = """
<!DOCTYPE html>

<html>

<head>
  <meta charset='utf-8'>
  <meta content='width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no' name='viewport'>
  <title>Deployment Not Found</title>
  <style>
    :root {
      --colorDefaultTextColor: #A3A9AC;
      --colorDefaultTextColorCard: #2D3B41;
      --colorBgApp: rgb(14, 30, 37);
      --colorBgInverse: hsl(175, 48%, 98%);
      --colorTextMuted: rgb(100, 110, 115);
      --colorError: #D32254;
      --colorBgCard: #fff;
      --colorShadow: #0e1e251f;
      --colorErrorText: rgb(142, 11, 48);
      --colorCardTitleCard: #2D3B41;
      --colorStackText: #222;
      --colorCodeText: #F5F5F5
    }

    :root {
      --background: 164 62% 99%;
      --foreground: 164 67% 0%;
      --muted: 164 7% 89%;
      --muted-foreground: 164 0% 26%;
      --popover: 164 62% 99%;
      --popover-foreground: 164 67% 0%;
      --card: 219, 40%, 18%;
      --toggle: 180, 23%, 95%;
      --card-foreground: 164 67% 0%;
      --border: 164 9% 90%;
      --input: 164 9% 90%;
      --primary: 164 61% 70%;
      --primary-foreground: 164 61% 10%;
      --secondary: 201 94% 80%;
      --secondary-foreground: 201 94% 20%;
      --accent: 164 10% 85%;
      --accent-foreground: 164 10% 25%;
      --destructive: 11 98% 31%;
      --destructive-foreground: 11 98% 91%;
      --ring: 164 61% 70%;
      --radius: 0.5rem;
      --loader: #003c57;
      --status-success: #bbf7d0;
      --status-error: #fecaca;
      --status-warning: #fef08a
    }

    @media (prefers-color-scheme:dark) {
      :root {
        --background: 226 19% 13%;
        --foreground: 231 28% 73%;
        --muted: 226 12% 17%;
        --muted-foreground: 226 12% 67%;
        --popover: 226 19% 10%;
        --popover-foreground: 231 28% 83%;
        --card: 164 43% 2%;
        --card-foreground: 164 30% 100%;
        --border: 226 9% 18%;
        --input: 226 9% 21%;
        --primary: 164 61% 70%;
        --primary-foreground: 164 61% 10%;
        --secondary: 201 94% 80%;
        --secondary-foreground: 201 94% 20%;
        --accent: 164 18% 21%;
        --accent-foreground: 164 18% 81%;
        --destructive: 11 98% 56%;
        --destructive-foreground: 0 0% 100%;
        --toggle: 164 43% 2%;
        --ring: 164 61% 70%;
        --loader: white
      }
    }

    body {
      font-family: -apple-system, BlinkMacSystemFont, segoe ui, Roboto, Helvetica, Arial, sans-serif, apple color emoji, segoe ui emoji, segoe ui symbol;
      background: hsl(var(--background));
      overflow: hidden;
      margin: 0;
      padding: 0;
      font-size: 1rem;
      line-height: 1.5
    }

    h1 {
      margin: 0;
      font-size: 1.375rem;
      line-height: 1.2
    }

    .main {
      position: relative;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      height: 100vh;
      width: 100vw
    }

    .card {
      position: relative;
      display: flex;
      flex-direction: column;
      width: 75%;
      max-width: 500px;
      padding: 24px;
      background: hsl(var(--card));
      color: #fff;
      border-radius: 8px;
      box-shadow: 0 2px 4px rgba(14, 30, 37, .16)
    }

    p:last-of-type {
      margin-bottom: 0
    }
  </style>
</head>

<body>
  <div class='main'>
    <div class='card'>
      <div class='header'>
        <h1>Deployment Not Found 🤷</h1>
      </div>
      <div class='body'>
        <p>Looks like you've followed a broken link or entered a URL that doesn't exist yet on ZaneOps.
      </div>
    </div>
  </div>
</body>

</html>
"""

DEFAULT_502_FALLBACK = """
<!DOCTYPE html>
<html>

<head>
  <meta charset='utf-8'>
  <meta content='width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no' name='viewport'>
  <title>Deployment Unavailable</title>
  <style>
    :root {
      --colorDefaultTextColor: #A3A9AC;
      --colorDefaultTextColorCard: #2D3B41;
      --colorBgApp: rgb(14, 30, 37);
      --colorBgInverse: hsl(175, 48%, 98%);
      --colorTextMuted: rgb(100, 110, 115);
      --colorError: #D32254;
      --colorBgCard: #fff;
      --colorShadow: #0e1e251f;
      --colorErrorText: rgb(142, 11, 48);
      --colorCardTitleCard: #2D3B41;
      --colorStackText: #222;
      --colorCodeText: #F5F5F5
    }

    :root {
      --background: 164 62% 99%;
      --foreground: 164 67% 0%;
      --muted: 164 7% 89%;
      --muted-foreground: 164 0% 26%;
      --popover: 164 62% 99%;
      --popover-foreground: 164 67% 0%;
      --card: 219, 40%, 18%;
      --toggle: 180, 23%, 95%;
      --card-foreground: 164 67% 0%;
      --border: 164 9% 90%;
      --input: 164 9% 90%;
      --primary: 164 61% 70%;
      --primary-foreground: 164 61% 10%;
      --secondary: 201 94% 80%;
      --secondary-foreground: 201 94% 20%;
      --accent: 164 10% 85%;
      --accent-foreground: 164 10% 25%;
      --destructive: 11 98% 31%;
      --destructive-foreground: 11 98% 91%;
      --ring: 164 61% 70%;
      --radius: 0.5rem;
      --loader: #003c57;
      --status-success: #bbf7d0;
      --status-error: #fecaca;
      --status-warning: #fef08a
    }

    @media (prefers-color-scheme:dark) {
      :root {
        --background: 226 19% 13%;
        --foreground: 231 28% 73%;
        --muted: 226 12% 17%;
        --muted-foreground: 226 12% 67%;
        --popover: 226 19% 10%;
        --popover-foreground: 231 28% 83%;
        --card: 164 43% 2%;
        --card-foreground: 164 30% 100%;
        --border: 226 9% 18%;
        --input: 226 9% 21%;
        --primary: 164 61% 70%;
        --primary-foreground: 164 61% 10%;
        --secondary: 201 94% 80%;
        --secondary-foreground: 201 94% 20%;
        --accent: 164 18% 21%;
        --accent-foreground: 164 18% 81%;
        --destructive: 11 98% 56%;
        --destructive-foreground: 0 0% 100%;
        --toggle: 164 43% 2%;
        --ring: 164 61% 70%;
        --loader: white
      }
    }

    body {
      font-family: -apple-system, BlinkMacSystemFont, segoe ui, Roboto, Helvetica, Arial, sans-serif, apple color emoji, segoe ui emoji, segoe ui symbol;
      background: hsl(var(--background));
      overflow: hidden;
      margin: 0;
      padding: 0;
      font-size: 1rem;
      line-height: 1.5
    }

    h1 {
      margin: 0;
      font-size: 1.375rem;
      line-height: 1.2
    }

    .main {
      position: relative;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      height: 100vh;
      width: 100vw
    }

    .card {
      position: relative;
      display: flex;
      flex-direction: column;
      width: 75%;
      max-width: 500px;
      padding: 24px;
      background: hsl(var(--card));
      color: #fff;
      border-radius: 8px;
      box-shadow: 0 2px 4px rgba(14, 30, 37, .16)
    }

    p:last-of-type {
      margin-bottom: 0
    }
  </style>

</head>

<body>
  <div class='main'>
    <div class='card'>
      <div class='header'>
        <h1>Deployment Unavailable ❌</h1>
      </div>
      <div class='body'>
        <p>Looks like you've followed a link to a deployment that has been removed or is not yet available.
      </div>
    </div>
  </div>
</body>

</html>
"""


def register_zaneops_app_on_proxy(
    proxy_url: str,
    zane_app_domain: str,
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
                                    "upstreams": [{"dial": zane_front_internal_domain}],
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
                f"[{Colors.BLUE}{config_id}{Colors.ENDC}] Updated proxy configuration succesfully ✅"
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
                    "endpoint": f"http://{zane_front_internal_domain}/api/_proxy/check-certiticates",
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
            f"[{Colors.BLUE}root.apps.tls{Colors.ENDC}] Updated proxy configuration succesfully ✅"
        )
    else:
        print(
            f"[{Colors.RED}root.apps.tls{Colors.ENDC}] ❌ Got an error when trying to update the proxy ❌"
        )
        print(f"With status code : {Colors.RED}{response.status_code}{Colors.ENDC}")
        print(f"With response data : {Colors.ORANGE}{response.text}{Colors.ENDC}\n")

    default_404_config = {
        "@id": "zane-catchall-404",
        "handle": [
            {
                "handler": "headers",
                "response": {
                    "set": {"Content-Type": ["text/html"]},
                    "add": {
                        "server": ["zaneops"],
                        "x-zane-request-id": ["{http.request.uuid}"],
                    },
                },
            },
            {
                "body": DEFAULT_404_FALLBACK,
                "handler": "static_response",
                "status_code": 404,
            },
        ],
    }
    response = requests.patch(
        f"{proxy_url}/id/zane-catchall-404", timeout=5, json=default_404_config
    )
    if 200 <= response.status_code < 300:
        print(
            f"[{Colors.BLUE}zane-catchall-404{Colors.ENDC}] Updated proxy configuration succesfully ✅"
        )
    else:
        print(
            f"[{Colors.RED}zane-catchall-404{Colors.ENDC}] ❌ Got an error when trying to update the proxy ❌"
        )
        print(f"With status code : {Colors.RED}{response.status_code}{Colors.ENDC}")
        print(f"With response data : {Colors.ORANGE}{response.text}{Colors.ENDC}\n")

    default_502_config = {
        "@id": "zane-error-502",
        "match": [{"expression": "{http.error.status_code} in [502]"}],
        "handle": [
            {
                "handler": "headers",
                "response": {
                    "set": {"Content-Type": ["text/html"]},
                    "add": {
                        "server": ["zaneops"],
                        "x-zane-request-id": ["{http.request.uuid}"],
                    },
                },
            },
            {
                "body": DEFAULT_502_FALLBACK,
                "handler": "static_response",
            },
        ],
    }
    response = requests.get(f"{proxy_url}/id/zane-server/errors", timeout=5)
    if response.status_code == 404 or response.json() is None:
        response = requests.put(
            f"{proxy_url}/id/zane-server/errors",
            json={"routes": [default_502_config]},
            timeout=5,
        )
    else:
        response = requests.patch(
            f"{proxy_url}/id/zane-server/errors/routes/0",
            json=default_502_config,
            timeout=5,
        )

    if 200 <= response.status_code < 300:
        print(
            f"[{Colors.BLUE}zane-catchall-502{Colors.ENDC}] Updated proxy configuration succesfully ✅"
        )
    else:
        print(
            f"[{Colors.RED}zane-catchall-502{Colors.ENDC}] ❌ Got an error when trying to update the proxy ❌"
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
