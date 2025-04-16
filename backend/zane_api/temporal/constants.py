CADDYFILE_BASE_STATIC = """# this file is read-only
:80 {
	# Set the root directory for static files
	root * /var/www/html
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

COPY ./{{publish.dir}}/ /var/www/html/
COPY ./Caddyfile /etc/caddy/Caddyfile
"""


DOCKERFILE_NIXPACKS_STATIC = """
# Webapp based on caddy
FROM caddy:alpine AS production

WORKDIR /var/www/html

# `/app/` is the output directory of nixpacks files
COPY --from=builder {{publish.dir}} /var/www/html/ 
COPY ./Caddyfile /etc/caddy/Caddyfile
"""

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
        },
        "caddy": {
            "inputs": [{"step": "packages:caddy"}],
            "commands": [
                {"path": "/etc/Caddyfile", "name": "Caddyfile"},
                {"cmd": "caddy fmt --overwrite /etc/Caddyfile"},
            ],
            "assets": {"Caddyfile": "{{caddyfile.contents}}"},
            "deployOutputs": [{"include": ["/etc/Caddyfile"]}],
        },
        "copy-build-files": {
            "inputs": [{"step": "build"}],
            "commands": [{"src": "dist", "dest": "/var/www/html"}],
            "deployOutputs": [{"include": ["/var/www/html"]}],
        },
    },
    "deploy": {
        "startCommand": "caddy run --config /etc/Caddyfile --adapter caddyfile 2\u003e\u00261"
    },
}


SERVER_RESOURCE_LIMIT_COMMAND = (
    "sh -c 'nproc && grep MemTotal /proc/meminfo | awk \"{print \\$2 * 1024}\"'"
)
VOLUME_SIZE_COMMAND = "sh -c 'df -B1 /mnt | tail -1 | awk \"{{print \\$2}}\"'"
ONE_HOUR = 3600  # seconds

REPOSITORY_CLONE_LOCATION = "repo"

NIXPACKS_BINARY_PATH = "/usr/local/bin/nixpacks"
DOCKER_BINARY_PATH = "/usr/bin/docker"
RAILPACK_BINARY_PATH = "/usr/local/bin/railpack"
