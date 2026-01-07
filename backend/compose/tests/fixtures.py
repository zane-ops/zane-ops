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
        zane.http.routes.0.port: "80"
        zane.http.routes.0.domain: "hello.127-0-0-1.sslip.io"
        zane.http.routes.0.base_path: "/"
"""

DOCKER_COMPOSE_MULTIPLE_ROUTES = """
services:
  api:
    image: myapi:latest
    deploy:
      labels:
        zane.http.routes.0.port: "3000"
        zane.http.routes.0.domain: "api.example.com"
        zane.http.routes.0.base_path: "/"
        zane.http.routes.0.strip_prefix: "false"
        zane.http.routes.1.port: "3001"
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
x-env:
  POSTGRES_USER: "{{ generate_username }}"
  POSTGRES_PASSWORD: "{{ generate_secure_password }}"
  POSTGRES_DB: "{{ generate_random_slug }}"
  API_TOKEN: "{{ generate_random_chars_32 }}"
  SECRET_KEY: "{{ generate_random_chars_64 }}"

services:
  db:
    image: postgres
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
  app:
    image: python
    environment:
      API_TOKEN: ${API_TOKEN}
      SECRET_KEY: ${SECRET_KEY}
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
        zane.http.routes.0.port: "80"
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

INVALID_COMPOSE_ROUTE_MISSING_PORT = """
services:
  web:
    image: nginx:alpine
    deploy:
      labels:
        zane.http.routes.0.domain: "example.com"
        zane.http.routes.0.base_path: "/"
"""

INVALID_COMPOSE_ROUTE_MISSING_DOMAIN = """
services:
  web:
    image: nginx:alpine
    deploy:
      labels:
        zane.http.routes.0.port: "80"
        zane.http.routes.0.base_path: "/"
"""

INVALID_COMPOSE_ROUTE_INVALID_PORT_ZERO = """
services:
  web:
    image: nginx:alpine
    deploy:
      labels:
        zane.http.routes.0.port: "0"
        zane.http.routes.0.domain: "example.com"
        zane.http.routes.0.base_path: "/"
"""

INVALID_COMPOSE_ROUTE_INVALID_PORT_NEGATIVE = """
services:
  web:
    image: nginx:alpine
    deploy:
      labels:
        zane.http.routes.0.port: "-1"
        zane.http.routes.0.domain: "example.com"
        zane.http.routes.0.base_path: "/"
"""

INVALID_COMPOSE_X_ENV_NOT_DICT = """
x-env:
  - SERVICE_PASSWORD_POSTGRES
  - SERVICE_USER_POSTGRES

services:
  db:
    image: postgres:14-alpine
"""

DOCKER_COMPOSE_WITH_X_ENV_OVERRIDES = """
x-env:
  SERVICE_PASSWORD_POSTGRES: "{{ generate_secure_password }}"
  SERVICE_PASSWORD_REDIS: "{{ generate_secure_password }}"
  SERVICE_USER_POSTGRES: "openpanel"
  OPENPANEL_POSTGRES_DB: "openpanel-db"
  MAIN_DOMAIN: "openpanel.127-0-0-1.sslip.io"
  API_DOMAIN: "api.openpanel.127-0-0-1.sslip.io"
  SERVICE_FQDN_OPDASHBOARD: "http://${MAIN_DOMAIN}"
  SERVICE_FQDN_OPAPI: "http://${API_DOMAIN}"
  DATABASE_URL: "postgres://${SERVICE_USER_POSTGRES}:${SERVICE_PASSWORD_POSTGRES}@db:5432/${OPENPANEL_POSTGRES_DB}"

services:
  db:
    image: postgres:14-alpine
    environment:
      POSTGRES_USER: ${SERVICE_USER_POSTGRES}
      POSTGRES_PASSWORD: ${SERVICE_PASSWORD_POSTGRES}
      POSTGRES_DB: ${OPENPANEL_POSTGRES_DB}

  api:
    image: myapi:latest
    environment:
      DATABASE_URL: ${DATABASE_URL}
      DASHBOARD_URL: ${SERVICE_FQDN_OPDASHBOARD}
      API_URL: ${SERVICE_FQDN_OPAPI}
"""

DOCKER_COMPOSE_WITH_X_ENV_IN_CONFIGS = """
x-env:
  APP_SECRET: "{{ generate_secure_password }}"
  APP_NAME: "myapp"
  APP_PORT: "8080"
  APP_HOST: "app.example.com"
  APP_URL: "http://${APP_HOST}:${APP_PORT}"

services:
  app:
    image: nginx:alpine
    configs:
      - source: app_config
        target: /etc/nginx/conf.d/default.conf

configs:
  app_config:
    content: |
      server {
        listen ${APP_PORT};
        server_name ${APP_HOST};

        location / {
          proxy_pass ${APP_URL};
          proxy_set_header X-App-Name "${APP_NAME}";
          proxy_set_header X-App-Secret "${APP_SECRET}";
        }
      }
"""

DOCKER_COMPOSE_WITH_X_ENV_IN_URLS = """
x-env:
  APP_DOMAIN: "myapp.com"
  API_DOMAIN: "api.${APP_DOMAIN}"
  API_PORT: "3000"
  DASHBOARD_DOMAIN: "dashboard.${APP_DOMAIN}"

services:
  api:
    image: myapi:latest
    deploy:
      labels:
        zane.http.routes.0.port: $API_PORT
        zane.http.routes.0.domain: $API_DOMAIN

  dashboard:
    image: mydashboard:latest
    deploy:
      labels:
        zane.http.routes.0.port: "8080"
        zane.http.routes.0.domain: "${DASHBOARD_DOMAIN}"
        zane.http.routes.0.base_path: "/"
"""
