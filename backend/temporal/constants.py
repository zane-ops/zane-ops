CADDYFILE_BASE_STATIC = """# this file is read-only
:{$PORT:80} {
	# Set the root directory for static files
	root * {$PUBLIC_ROOT:/var/www/html}
	file_server {{custom.index}}{{custom.not_found}}
}
"""

CADDYFILE_CUSTOM_NOT_FOUND_PAGE = """

	# Set the page to show in case of 404 error
	handle_errors {
		@404 {
			expression {http.error.status_code} == 404
		}
		rewrite @404 {{page.not_found}}
		file_server
	}"""

CADDYFILE_CUSTOM_INDEX_PAGE = """

	# Set the index page to redirect all requests to
	try_files {path} {{page.index}}"""

DOCKERFILE_STATIC = """
# Webapp based on caddy
FROM caddy:alpine

WORKDIR /var/www/html

ENV PUBLIC_ROOT=/var/www/html

COPY ./{{publish.dir}}/ /var/www/html/
COPY ./Caddyfile /etc/caddy/Caddyfile
"""


DOCKERFILE_NIXPACKS_STATIC = """
# Webapp based on caddy
FROM caddy:alpine AS production

WORKDIR /var/www/html

ENV PUBLIC_ROOT=/var/www/html

# `/app/` is the output directory of nixpacks files
COPY --from=builder {{publish.dir}} /var/www/html/ 
COPY ./Caddyfile /etc/caddy/Caddyfile
"""

RAILPACK_CONFIG_BASE = {
    "$schema": "https://schema.railpack.com",
}


RAILPACK_STATIC_CONFIG = {
    "$schema": "https://schema.railpack.com",
    "steps": {
        "packages:caddy": {
            "inputs": [{"image": "ghcr.io/railwayapp/railpack-builder:latest"}],
            "commands": [
                {"cmd": "mise install-into caddy@2.9.1 /railpack/caddy"},
                {"path": "/railpack/caddy"},
                {"path": "/railpack/caddy/bin"},
            ],
            "deployOutputs": [{"include": ["/railpack/caddy"]}],
            "secrets": [],
        },
        "caddy": {
            "inputs": [{"step": "packages:caddy"}],
            "commands": [
                {"path": "/Caddyfile", "name": "Caddyfile"},
                {"cmd": "caddy fmt --overwrite /Caddyfile"},
            ],
            "assets": {"Caddyfile": "{{caddyfile.contents}}"},
            "deployOutputs": [{"include": ["/Caddyfile"]}],
            "secrets": [],
        },
        "build:export": {
            "inputs": [{"step": "build"}],
            "deployOutputs": [{"include": ["{{publish.dir}}"]}],
            "secrets": [],
        },
    },
    "deploy": {
        "startCommand": "caddy run --config /Caddyfile --adapter caddyfile 2\u003e\u00261",
        "variables": {"PUBLIC_ROOT": "{{publish.dir}}"},
    },
}


SERVER_RESOURCE_LIMIT_COMMAND = (
    "sh -c 'nproc && grep MemTotal /proc/meminfo | awk \"{print \\$2 * 1024}\"'"
)
VOLUME_SIZE_COMMAND = "sh -c 'df -B1 /mnt | tail -1 | awk \"{{print \\$2}}\"'"

REPOSITORY_CLONE_LOCATION = "repo"

NIXPACKS_BINARY_PATH = "/usr/local/bin/nixpacks"
DOCKER_BINARY_PATH = "/usr/bin/docker"
RAILPACK_BINARY_PATH = "/usr/local/bin/railpack"

# for when ZaneOps scales down a service and puts it to sleep during deployment
ZANEOPS_SLEEP_DEPLOY_MARKER = "[zaneops::internal::service_paused_for_deployment]"

# for when a user manually puts a service to sleep
ZANEOPS_SLEEP_MANUAL_MARKER = "[zaneops::internal::service_paused_by_user]"

# for when a service is resumed (system or user)
ZANEOPS_RESUME_DEPLOY_MARKER = "[zaneops::internal::service_resumed_after_deployment]"
ZANEOPS_RESUME_MANUAL_MARKER = "[zaneops::internal::service_resumed_by_user]"


SERVICE_DEPLOY_SEMAPHORE_KEY = "deploy-service-workflow"
STACK_DEPLOY_SEMAPHORE_KEY = "deploy-stack-workflow"

ZANEOPS_ONGOING_UPDATE_CACHE_KEY = "[zaneops::internal::on-going-update]"

SERVICE_DETECTED_PORTS_CACHE_KEY = "service_detected_ports"

BUILD_REGISTRY_VOLUME_PATH = "/var/lib/registry"
BUILD_REGISTRY_CONFIG_PATH = "/etc/distribution/config.yml"
BUILD_REGISTRY_PASSWORD_PATH = "/auth/htpasswd"
BUILD_REGISTRY_IMAGE = "registry:3.0.0"
BUILD_REGISTRY_DEPLOY_SEMAPHORE_KEY = "deploy-registry-workflow"

ZANE_BUILDER_NAME_PREFIX = "builder-zane"


DEFAULT_CADDY_LOGGING = {
    "logs": {
        "default": {
            "writer": {"output": "stdout"},
            "encoder": {"format": "json"},
        }
    }
}
DEFAULT_CADDY_CERT_STORAGE = {
    "address": ["zane.valkey:6379"],
    "db": 1,
    "timeout": "5",
    "module": "redis",
}
DEFAULT_ADMIN_CONFIG = {
    "config": {
        # This module is used for reloading the next caddy config
        # REQUIRED to keep the config in sync on the proxy
        "load": {
            "header": {"Authorization": ["Internal {env.DJANGO_SECRET_KEY}"]},
            "module": "http",
            "url": "http://{env.API_HOST}/api/_proxy/config/",
        },
        "load_delay": "5s",
    }
}


FALLBACK_404_HTML = """
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

FALLBACK_502_HTML = """
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

DEFAULT_502_CONFIG = {
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
            "body": FALLBACK_502_HTML,
            "handler": "static_response",
        },
    ],
}

DEFAULT_404_CONFIG = {
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
            "body": FALLBACK_404_HTML,
            "handler": "static_response",
            "status_code": 404,
        },
    ],
}
