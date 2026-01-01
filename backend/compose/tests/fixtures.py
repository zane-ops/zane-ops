"""
Docker Compose test fixtures representing real-world use cases.
"""

DOCKER_COMPOSE_SIMPLE_DB = """
services:
  postgres:
    image: postgres:18-alpine
    environment:
      POSTGRES_PASSWORD: supersecret
      POSTGRES_DB: myapp
    volumes:
      - db-data:/var/lib/postgresql

volumes:
  db-data:
"""

DOCKER_COMPOSE_WEB_SERVICE = """
services:
  web:
    image: nginxdemos/hello:latest
    deploy:
      labels:
        zane.http.port: "80"
        zane.http.routes.0.domain: "hello.127-0-0-1.sslip.io"
        zane.http.routes.0.base_path: "/"
"""

DOCKER_COMPOSE_MULTIPLE_ROUTES = """
services:
  api:
    image: myapi:latest
    deploy:
      labels:
        zane.http.port: "3000"
        zane.http.routes.0.domain: "api.example.com"
        zane.http.routes.0.base_path: "/"
        zane.http.routes.0.strip_prefix: "false"
        zane.http.routes.1.domain: "example.com"
        zane.http.routes.1.base_path: "/api"
        zane.http.routes.1.strip_prefix: "true"
"""

DOCKER_COMPOSE_WITH_DEPENDS_ON = """
services:
  web:
    image: django:latest
    depends_on:
      - db
      - cache

  db:
    image: postgres:16-alpine

  cache:
    image: redis:7-alpine
"""


DOCKER_COMPOSE_EXTERNAL_VOLUME = """
services:
  app:
    image: myapp:latest
    volumes:
      - shared_data:/app/data

volumes:
  shared_data:
    external: true
"""

DOCKER_COMPOSE_WITH_HOST_VOLUME = """
services:
  portainer:
    image: portainer-ce:latest
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
"""


DOCKER_COMPOSE_WITH_PLACEHOLDERS = """
services:
  db:
    image: postgres
    environment:
      POSTGRES_USER: '{{generate_username}}'
      POSTGRES_PASSWORD: '{{ generate_secure_password}}'
      POSTGRES_DB: '{{ generate_random_slug }}'
  app:
    image: python
    environment:
      API_TOKEN: '{{ generate_random_chars_32 }}'
      SECRET_KEY: '{{ generate_random_chars_64 }}'
"""

DOCKER_COMPOSE_WITH_EXTERNAL_CONFIGS = """
services:
  web:
    image: nginx:alpine
    configs:
      - source: nginx_config
        target: /etc/nginx/nginx.conf
      - source: site_config
        target: /etc/nginx/conf.d/default.conf
    deploy:
      labels:
        zane.http.port: "80"
        zane.http.routes.0.domain: "example.com"
        zane.http.routes.0.base_path: "/"

configs:
  nginx_config:
    external: true
  site_config:
    external: true
"""

DOCKER_COMPOSE_WITH_INLINE_CONFIGS = """
services:
  web:
    image: nginx:alpine
    configs:
      - source: nginx_config
        target: /etc/nginx/nginx.conf

configs:
  nginx_config:
    content: |
      user nginx;
      worker_processes auto;
      events {
        worker_connections 1024;
      }
"""


DOCKER_COMPOSE_MINIMAL = """
services:
  redis:
    image: valkey/valkey:alpine
"""


INVALID_COMPOSE_NO_IMAGE = """
services:
  app:
    command: echo "Hello World"
    build:
      context: .
      dockerfile: Dockerfile
"""


INVALID_COMPOSE_RELATIVE_BIND_VOLUME = """
services:
  myapp:
    image: postgres:alpine
    volumes:
      - ../../db-data:/var/lib/postgresql
"""

INVALID_COMPOSE_SERVICE_NAME_SPECIAL = """
services:
  my@app:
    image: myapp:latest
"""

INVALID_COMPOSE_YAML_SYNTAX = """
services:
  app:
    image: myapp:latest
  environment:
    NODE_ENV: production
"""

INVALID_COMPOSE_EMPTY = ""

INVALID_COMPOSE_NO_SERVICES = """
networks:
  default:
"""

INVALID_COMPOSE_EMPTY_SERVICES = """
services: {}
networks:
  default:
"""

INVALID_COMPOSE_SERVICES_NOT_DICT = """
services:
  - app
  - db
"""


INVALID_COMPOSE_WITH_CONFIG_FILE_LOCATION = """
services:
  web:
    image: nginx:alpine
    configs:
      - source: app_settings
        target: /app/config.json

configs:
  app_settings:
    file: /config/settings.json
"""
