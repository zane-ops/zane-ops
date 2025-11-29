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

ZANEOPS_ONGOING_UPDATE_CACHE_KEY = "[zaneops::internal::on-going-update]"

SERVICE_DETECTED_PORTS_CACHE_KEY = "service_detected_ports"

BUILD_REGISTRY_VOLUME_PATH = "/var/lib/registry"
BUILD_REGISTRY_CONFIG_PATH = "/etc/distribution/config.yml"
BUILD_REGISTRY_PASSWORD_PATH = "/auth/htpasswd"
BUILD_REGISTRY_IMAGE = "registry:3.0.0"
BUILD_REGISTRY_DEPLOY_SEMAPHORE_KEY = "deploy-registry-workflow"
