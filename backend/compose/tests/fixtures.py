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
  POSTGRES_PASSWORD: "{{ generate_password_64 }}"
  POSTGRES_DB: "{{ generate_slug }}"
  API_TOKEN: "{{ generate_password_32 }}"
  SECRET_KEY: "{{ generate_password_64 }}"

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

DOCKER_COMPOSE_WITH_GENERATE_DOMAIN = """
x-env:
  APP_DOMAIN: "{{ generate_domain }}"
  API_URL: "http://${APP_DOMAIN}/api"

services:
  web:
    image: nginx:alpine
    environment:
      APP_DOMAIN: ${APP_DOMAIN}
      API_URL: ${API_URL}
    deploy:
      labels:
        zane.http.routes.0.port: "80"
        zane.http.routes.0.domain: "${APP_DOMAIN}"
        zane.http.routes.0.base_path: "/"
"""

DOCKER_COMPOSE_WITH_PASSWORD_PLACEHOLDERS = """
x-env:
  SHORT_PASSWORD: "{{ generate_password_32 }}"
  LONG_PASSWORD: "{{ generate_password_64 }}"
  DB_PASSWORD: "{{ generate_password_64 }}"

services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_PASSWORD: ${DB_PASSWORD}
  app:
    image: myapp:latest
    environment:
      SHORT_TOKEN: ${SHORT_PASSWORD}
      LONG_SECRET: ${LONG_PASSWORD}
"""

DOCKER_COMPOSE_WITH_BASE64_PLACEHOLDERS = """
x-env:
  SHORT_BASE64: "{{ generate_base64_32 }}"
  LONG_BASE64: "{{ generate_base64_64 }}"
  JWT_SECRET: "{{ generate_base64_64 }}"

services:
  app:
    image: myapp:latest
    environment:
      SHORT_TOKEN: ${SHORT_BASE64}
      LONG_SECRET: ${LONG_BASE64}
      JWT_SECRET: ${JWT_SECRET}
"""

DOCKER_COMPOSE_WITH_CUSTOM_LENGTH_PLACEHOLDERS = """
x-env:
  CUSTOM_SLUG_8: "{{ generate_slug_8 }}"
  CUSTOM_SLUG_16: "{{ generate_slug_16 }}"
  CUSTOM_PASSWORD_16: "{{ generate_password_16 }}"
  CUSTOM_PASSWORD_128: "{{ generate_password_128 }}"
  CUSTOM_BASE64_24: "{{ generate_base64_24 }}"
  CUSTOM_BASE64_48: "{{ generate_base64_48 }}"
  CUSTOM_USERNAME_8: "{{ generate_username_8 }}"
  CUSTOM_USERNAME_16: "{{ generate_username_16 }}"

services:
  app:
    image: myapp:latest
    environment:
      SLUG_8: ${CUSTOM_SLUG_8}
      SLUG_16: ${CUSTOM_SLUG_16}
      PASSWORD_16: ${CUSTOM_PASSWORD_16}
      PASSWORD_128: ${CUSTOM_PASSWORD_128}
      BASE64_24: ${CUSTOM_BASE64_24}
      BASE64_48: ${CUSTOM_BASE64_48}
      USERNAME_8: ${CUSTOM_USERNAME_8}
      USERNAME_16: ${CUSTOM_USERNAME_16}
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

DOCKER_COMPOSE_ROUTE_MISSING_DOMAIN = """
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
  SERVICE_PASSWORD_POSTGRES: "{{ generate_password_64 }}"
  SERVICE_PASSWORD_REDIS: "{{ generate_password_64 }}"
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
  APP_SECRET: "{{ generate_password_64 }}"
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


# Fixtures for URL conflict tests
def compose_with_url(domain: str, base_path: str = "/", port: int = 80) -> str:
    return f"""
services:
  web:
    image: nginx:alpine
    deploy:
      labels:
        zane.http.routes.0.port: "{port}"
        zane.http.routes.0.domain: "{domain}"
        zane.http.routes.0.base_path: "{base_path}"
"""


INVALID_DOCKER_COMPOSE_DUPLICATE_URLS = """
services:
  web:
    image: nginx:alpine
    deploy:
      labels:
        zane.http.routes.0.port: "80"
        zane.http.routes.0.domain: "duplicate.example.com"
        zane.http.routes.0.base_path: "/"
  api:
    image: nginx:alpine
    deploy:
      labels:
        zane.http.routes.0.port: "3000"
        zane.http.routes.0.domain: "duplicate.example.com"
        zane.http.routes.0.base_path: "/"
"""

INVALID_DOCKER_COMPOSE_WIDLCARD_SHADOW_URLS = """
services:
  api:
    image: nginx:alpine
    deploy:
      labels:
        zane.http.routes.0.port: "3000"
        zane.http.routes.0.domain: "duplicate.example.com"
        zane.http.routes.0.base_path: "/"
  web:
    image: nginx:alpine
    deploy:
      labels:
        zane.http.routes.0.port: "80"
        zane.http.routes.0.domain: "*.example.com"
        zane.http.routes.0.base_path: "/"

"""
