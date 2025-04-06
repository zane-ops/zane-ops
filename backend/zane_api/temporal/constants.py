CADDYFILE_BASE_STATIC = """
:80 {
	# Set the root directory for static files
	root * /srv
	file_server

    {{custom.index}}

    {{custom.not_found}}
}
"""

CADDYFILE_CUSTOM_NOT_FOUND_PAGE = """
	handle_errors {
		@404 {
			expression {http.error.status_code} == 404
		}
		rewrite @404 {{page.not_found}}
		file_server
	}
"""

CADDYFILE_CUSTOM_INDEX_PAGE = """
	try_files {path} {{page.index}}
"""

DOCKERFILE_STATIC = """
# Webapp based on caddy
FROM caddy:alpine

WORKDIR /var/www/html

COPY ./dist/ /srv
COPY ./Caddyfile /etc/caddy/Caddyfile
"""
