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


SERVER_RESOURCE_LIMIT_COMMAND = (
    "sh -c 'nproc && grep MemTotal /proc/meminfo | awk \"{print \\$2 * 1024}\"'"
)
VOLUME_SIZE_COMMAND = "sh -c 'df -B1 /mnt | tail -1 | awk \"{{print \\$2}}\"'"
ONE_HOUR = 3600  # seconds

REPOSITORY_CLONE_LOCATION = "repo"
