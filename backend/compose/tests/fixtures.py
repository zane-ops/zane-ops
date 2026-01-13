"""
Docker Compose test fixtures representing real-world use cases.
"""

import base64
from dataclasses import asdict, dataclass
import json

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
x-zane-env:
  POSTGRES_USER: "{{ generate_username }}"
  POSTGRES_DB: "{{ generate_slug }}"
  POSTGRES_PASSWORD: "{{ generate_password | 16 }}"
  API_TOKEN: "{{ generate_password | 32 }}"
  SECRET_KEY: "{{ generate_password | 64 }}"

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
x-zane-env:
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


DOCKER_COMPOSE_WITH_CUSTOM_PASSWORD_LENGTH = """
x-zane-env:
  CUSTOM_PASSWORD_16: "{{ generate_password | 16 }}"
  CUSTOM_PASSWORD_128: "{{ generate_password | 128 }}"

services:
  app:
    image: myapp:latest
    environment:
      PASSWORD_16: ${CUSTOM_PASSWORD_16}
      PASSWORD_128: ${CUSTOM_PASSWORD_128}
"""


DOCKER_COMPOSE_WITH_BASE64_GENERATE = """
x-zane-env:
  BASE64_HELLO: "{{ generate_base64 | 'hello' }}"
  BASE64_BYE: "{{ generate_base64 | 'bye' }}"

services:
  app:
    image: myapp:latest
    environment:
      BASE64_HELLO: ${BASE64_HELLO}
      BASE64_BYE: ${BASE64_BYE}
"""

DOCKER_COMPOSE_WITH_UUID_GENERATE = """
x-zane-env:
  LICENCE_ID: "{{ generate_uuid }}"

services:
  app:
    image: myapp:latest
    environment:
      LICENCE_ID: ${LICENCE_ID}
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
x-zane-env:
  - SERVICE_PASSWORD_POSTGRES
  - SERVICE_USER_POSTGRES

services:
  db:
    image: postgres:14-alpine
"""

DOCKER_COMPOSE_WITH_X_ENV_OVERRIDES = """
x-zane-env:
  SERVICE_PASSWORD_POSTGRES: "{{ generate_password | 64 }}"
  SERVICE_PASSWORD_REDIS: "{{ generate_password | 64 }}"
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
x-zane-env:
  APP_SECRET: "{{ generate_password | 64 }}"
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
x-zane-env:
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


##====================================##
##   DOKPLOY COMPATIBILITY fixtures   ##
##====================================##


@dataclass
class DokployTemplate:
    compose: str
    config: str

    @property
    def to_dict(self):
        return asdict(self)

    @property
    def base64(self):
        return base64.b64encode(json.dumps(asdict(self)).encode()).decode()


DOKPLOY_POCKETBASE_TEMPLATE = DokployTemplate(
    compose="""
# IMPORTANT: Please update the admin credentials in your .env file
# Access PocketBase Admin UI at: https://your-domain.com/_/ (replace with your configured domain)
# Note: Admin UI may take up to 1 minute to load on first startup

version: "3.8"

services:
  pocketbase:
    image: adrianmusante/pocketbase:latest
    restart: always
    expose:
      - 8090
    volumes:
      - pocketbase-data:/pocketbase
    environment:
      - POCKETBASE_ADMIN_EMAIL=${ADMIN_EMAIL}
      - POCKETBASE_ADMIN_PASSWORD=${ADMIN_PASSWORD}
      - POCKETBASE_ADMIN_UPSERT=true
      - POCKETBASE_PORT_NUMBER=8090
      # Optional: Encryption key for securing app settings (OAuth2 secrets, SMTP passwords, etc.)
      # Uncomment and set a secure key in your .env file for production use
      # - POCKETBASE_ENCRYPTION_KEY=${ENCRYPTION_KEY}
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost:8090/_/"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  pocketbase-data: {}
""",
    config="""
[variables]
main_domain = "${domain}"
admin_email = "${email}"
admin_password = "${password:32}"

[config]
[[config.domains]]
serviceName = "pocketbase"
port = 8090
host = "${main_domain}"

[config.env]
ADMIN_EMAIL = "${admin_email}"
ADMIN_PASSWORD = "${admin_password}"

[[config.mounts]]
name = "pocketbase-data"
mountPath = "/pocketbase"
""",
)


DOKPLOY_VALKEY_TEMPLATE = DokployTemplate(
    compose="""
version: "3.8"

services:
  valkey:
    image: valkey/valkey:8.1.4
    restart: unless-stopped
    ports:
      - 6379
    volumes:
      - ../files/valkey.conf:/etc/valkey/valkey.conf
      - valkey-data:/data
    command: valkey-server /etc/valkey/valkey.conf
    environment:
      - VALKEY_PASSWORD=${VALKEY_PASSWORD}
    healthcheck:
      test: ["CMD-SHELL", 'valkey-cli -a "$$VALKEY_PASSWORD" ping | grep PONG']
      interval: 10s
      timeout: 3s
      retries: 5
      start_period: 10s

volumes:
  valkey-data: {}
""",
    config='''
[variables]
valkey_password = "${password:32}"

[config]
env = [
  "VALKEY_PASSWORD=${valkey_password}"
]

[[config.mounts]]
filePath = "valkey.conf"
content = """
# Valkey configuration file
# For more information, see: https://github.com/valkey-io/valkey

# Network
bind 0.0.0.0
port 6379
protected-mode yes

# General
daemonize no
supervised no
pidfile /data/valkey.pid
loglevel notice
logfile ""

# Snapshotting
save 900 1
save 300 10
save 60 10000
stop-writes-on-bgsave-error yes
rdbcompression yes
rdbchecksum yes
dbfilename dump.rdb
dir /data

# Replication
replica-serve-stale-data yes
replica-read-only yes

# Security
requirepass ${valkey_password}

# Memory management
maxmemory-policy noeviction

# Append only file
appendonly yes
appendfilename "appendonly.aof"
appendfsync everysec
no-appendfsync-on-rewrite no
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb
"""
''',
)

DOKPLOY_ARANGO_DB_TEMPLATE = DokployTemplate(
    compose="""
version: "3.8"
services:
  arangodb:
    image: arangodb:3.12.4
    restart: unless-stopped
    expose:
      - 8529
    ports:
      - 8529
      - 8530
    environment:
      - ARANGO_ROOT_PASSWORD=${ARANGO_PASSWORD}
    volumes:
      - data:/var/lib/arangodb3

volumes:
  data: {}
""",
    config="""
[variables]
main_domain = "${domain}"
arango_password = "${password:16}"

[config]
[[config.domains]]
serviceName = "arangodb"
port = 8529
host = "${main_domain}"

[config.env]
ARANGO_PASSWORD = "${arango_password}"
""",
)


DOKPLOY_RYBBIT_TEMPLATE = DokployTemplate(
    compose="""
# https://www.rybbit.io/docs/self-hosting-advanced

# NOTE: there are two sample HTTP traefik domain entries created:
# - rybbit_backend (port 3001, path /api), 
# - rybbit_client (port 3002, path /)
#
# You should treat these as placeholders - Rybbit only supports HTTPS.
#
# You should also update the `BASE_URL`, and `DOMAIN_NAME` environment
# variable when updating the domain entries with your custom domain.

services:
  rybbit_clickhouse:
    image: clickhouse/clickhouse-server:25.5
    volumes:
      - clickhouse_data:/var/lib/clickhouse
      - ../files/clickhouse_config:/etc/clickhouse-server/config.d
    environment:
      - CLICKHOUSE_DB=${CLICKHOUSE_DB}
      - CLICKHOUSE_USER=${CLICKHOUSE_USER}
      - CLICKHOUSE_PASSWORD=${CLICKHOUSE_PASSWORD}
    healthcheck:
      test:
        [
          "CMD",
          "wget",
          "--no-verbose",
          "--tries=1",
          "--spider",
          "http://localhost:8123/ping",
        ]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
    restart: unless-stopped

  rybbit_postgres:
    image: postgres:17.5
    environment:
      - POSTGRES_DB=${POSTGRES_DB}
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped

  rybbit_backend:
    image: ghcr.io/rybbit-io/rybbit-backend:v1.5.1
    environment:
      - NODE_ENV=production
      - CLICKHOUSE_HOST=http://rybbit_clickhouse:8123
      - CLICKHOUSE_DB=${CLICKHOUSE_DB}
      - CLICKHOUSE_USER=${CLICKHOUSE_USER}
      - CLICKHOUSE_PASSWORD=${CLICKHOUSE_PASSWORD}
      - POSTGRES_HOST=rybbit_postgres
      - POSTGRES_PORT=5432
      - POSTGRES_DB=${POSTGRES_DB}
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - BETTER_AUTH_SECRET=${BETTER_AUTH_SECRET}
      - BASE_URL=${BASE_URL}
      - DOMAIN_NAME=${DOMAIN_NAME}
      - DISABLE_SIGNUP=${DISABLE_SIGNUP}
    depends_on:
      rybbit_clickhouse:
        condition: service_healthy
      rybbit_postgres:
        condition: service_started
    healthcheck:
      test: ["CMD", "wget", "--no-verbose", "--tries=1", "--spider", "http://127.0.0.1:3001/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
    restart: unless-stopped

  rybbit_client:
    image: ghcr.io/rybbit-io/rybbit-client:v1.5.1
    environment:
      - NODE_ENV=production
      - NEXT_PUBLIC_BACKEND_URL=${BASE_URL}
      - DOMAIN_NAME=${DOMAIN_NAME}
      - NEXT_PUBLIC_DISABLE_SIGNUP=${DISABLE_SIGNUP}
    depends_on:
      - rybbit_backend
    restart: unless-stopped

volumes:
  clickhouse_data:
  postgres_data:
""",
    config='''
[variables]
main_domain = "${domain}"
better_auth_secret = "${password:32}"
clickhouse_password = "${password:32}"
postgres_password = "${password:32}"

[[config.domains]]
serviceName = "rybbit_backend"
port = 3001
host = "${main_domain}"
path = "/api"

[[config.domains]]
serviceName = "rybbit_client"
port = 3002
host = "${main_domain}"

[config.env]
BASE_URL = "http://${main_domain}"
DOMAIN_NAME= "${main_domain}"
BETTER_AUTH_SECRET = "${better_auth_secret}"
DISABLE_SIGNUP = "false"
CLICKHOUSE_DB = "analytics"
CLICKHOUSE_USER = "default"
CLICKHOUSE_PASSWORD = "${clickhouse_password}"
POSTGRES_DB = "analytics"
POSTGRES_USER = "frog"
POSTGRES_PASSWORD = "${postgres_password}"

[[config.mounts]]
filePath = "./clickhouse_config/enable_json.xml"
content = """
<clickhouse>
    <settings>
        <enable_json_type>1</enable_json_type>
    </settings>
</clickhouse>
"""

[[config.mounts]]
filePath = "./clickhouse_config/logging_rules.xml"
content = """
<clickhouse>
    <logger>
        <level>warning</level>
        <console>true</console>
    </logger>
    <query_thread_log remove="remove"/>
    <query_log remove="remove"/>
    <text_log remove="remove"/>
    <trace_log remove="remove"/>
    <metric_log remove="remove"/>
    <asynchronous_metric_log remove="remove"/>
    <session_log remove="remove"/>
    <part_log remove="remove"/>
    <latency_log remove="remove"/>
    <processors_profile_log remove="remove"/>
</clickhouse>
"""

[[config.mounts]]
filePath = "./clickhouse_config/network.xml"
content = """
<clickhouse>
    <listen_host>0.0.0.0</listen_host>
</clickhouse>
"""

[[config.mounts]]
filePath = "./clickhouse_config/user_logging.xml"
content = """
<clickhouse>
    <profiles>
        <default>
            <log_queries>0</log_queries>
            <log_query_threads>0</log_query_threads>
            <log_processors_profiles>0</log_processors_profiles>
        </default>
    </profiles>
</clickhouse>
"""
''',
)

DOKPLOY_OPENPANEL_TEMPLATE = DokployTemplate(
    compose="""x-database: &x-database
  DATABASE_URL: postgres://${SERVICE_USER_POSTGRES}:${SERVICE_PASSWORD_POSTGRES}@op-db:5432/${OPENPANEL_POSTGRES_DB}?schema=public
  DATABASE_URL_DIRECT: postgres://${SERVICE_USER_POSTGRES}:${SERVICE_PASSWORD_POSTGRES}@op-db:5432/${OPENPANEL_POSTGRES_DB}?schema=public
  REDIS_URL: redis://default:${SERVICE_PASSWORD_REDIS}@op-kv:6379
  CLICKHOUSE_URL: ${OPENPANEL_CLICKHOUSE_URL:-http://op-ch:8123/openpanel}

services:
  op-db:
    image: postgres:14-alpine
    restart: always
    volumes:
      - op-db-data:/var/lib/postgresql/data
    healthcheck:
      test: [ 'CMD-SHELL', 'pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}' ]
      interval: 10s
      timeout: 5s
      retries: 5
    environment:
      - POSTGRES_DB=${OPENPANEL_POSTGRES_DB}
      - POSTGRES_USER=${SERVICE_USER_POSTGRES}
      - POSTGRES_PASSWORD=${SERVICE_PASSWORD_POSTGRES}

  op-kv:
    image: redis:7.2.5-alpine
    restart: always
    volumes:
      - op-kv-data:/data
    command: redis-server --requirepass ${SERVICE_PASSWORD_REDIS} --maxmemory-policy noeviction
    healthcheck:
      test: [CMD, redis-cli, -a, "${SERVICE_PASSWORD_REDIS}", ping]
      interval: 10s
      timeout: 5s
      retries: 5

  op-ch:
    image: clickhouse/clickhouse-server:24.3.2-alpine
    restart: always
    volumes:
      - op-ch-data:/var/lib/clickhouse
      - op-ch-logs:/var/log/clickhouse-server
      - ../files/clickhouse/clickhouse-config.xml:/etc/clickhouse-server/config.d/op-config.xml:ro
      - ../files/clickhouse/clickhouse-user-config.xml:/etc/clickhouse-server/users.d/op-user-config.xml:ro
      - ../files/clickhouse/init-db.sql:/docker-entrypoint-initdb.d/1_init-db.sql:ro
    healthcheck:
      test: [CMD-SHELL, 'clickhouse-client --query "SELECT 1" -d openpanel']
      interval: 10s
      timeout: 5s
      retries: 5

  op-api:
    image: lindesvard/openpanel-api:${OP_API_VERSION:-latest}
    restart: always
    command: >
      sh -c "
        echo 'Waiting for PostgreSQL to be ready...'
        while ! nc -z op-db 5432; do
          sleep 1
        done
        echo 'PostgreSQL is ready'
      
        echo 'Waiting for ClickHouse to be ready...'
        while ! nc -z op-ch 8123; do
          sleep 1
        done
        echo 'ClickHouse is ready'
      
        echo 'Running migrations...'
        
        echo '$DATABASE_URL'
      
        CI=true pnpm -r run migrate:deploy
      
        pnpm start
      "
    environment:
      # Common
      NODE_ENV: production
      NEXT_PUBLIC_SELF_HOSTED: true
      # URLs
      SERVICE_FQDN_OPAPI: /api
      # Set coolify FQDN domain
      NEXT_PUBLIC_API_URL: $SERVICE_FQDN_OPAPI
      NEXT_PUBLIC_DASHBOARD_URL: $SERVICE_FQDN_OPDASHBOARD
      # Others
      COOKIE_SECRET: ${SERVICE_BASE64_COOKIESECRET}
      ALLOW_REGISTRATION: ${OPENPANEL_ALLOW_REGISTRATION:-false}
      ALLOW_INVITATION: ${OPENPANEL_ALLOW_INVITATION:-true}
      EMAIL_SENDER: ${OPENPANEL_EMAIL_SENDER}
      RESEND_API_KEY: ${RESEND_API_KEY}
      <<: *x-database
    healthcheck:
      test: [ "CMD-SHELL", "curl -f http://localhost:3000/healthcheck || exit 1" ]
      interval: 10s
      timeout: 5s
      retries: 5
    depends_on:
      op-db:
        condition: service_healthy
      op-ch:
        condition: service_healthy
      op-kv:
        condition: service_healthy

  op-dashboard:
    image: lindesvard/openpanel-dashboard:${OP_DASHBOARD_VERSION:-latest}
    restart: always
    depends_on:
      op-api:
        condition: service_healthy
    environment:
      # Common
      NODE_ENV: production
      NEXT_PUBLIC_SELF_HOSTED: true
      # URLs
      SERVICE_FQDN_OPDASHBOARD:
      # Set coolify FQDN domain
      NEXT_PUBLIC_API_URL: $SERVICE_FQDN_OPAPI
      NEXT_PUBLIC_DASHBOARD_URL: $SERVICE_FQDN_OPDASHBOARD
      <<: *x-database
    healthcheck:
      test: [ 'CMD-SHELL', 'curl -f http://localhost:3000/api/healthcheck || exit 1' ]
      interval: 10s
      timeout: 5s
      retries: 5

  op-worker:
    image: lindesvard/openpanel-worker:${OP_WORKER_VERSION:-latest}
    restart: always
    depends_on:
      op-api:
        condition: service_healthy
    environment:
      # FQDN
      SERVICE_FQDN_OPBULLBOARD:
      # Common
      NODE_ENV=production:
      NEXT_PUBLIC_SELF_HOSTED: true
      # Set coolify FQDN domain
      NEXT_PUBLIC_API_URL: $SERVICE_FQDN_OPAPI
      <<: *x-database
    healthcheck:
      test: [ 'CMD-SHELL', 'curl -f http://localhost:3000/healthcheck || exit 1' ]
      interval: 10s
      timeout: 5s
      retries: 5
    deploy:
      mode: replicated
      replicas: 1

volumes:
  op-db-data:
  op-kv-data:
  op-ch-data:
  op-ch-logs:
  op-proxy-data:
  op-proxy-config:
""",
    config='''[variables]
main_domain = "${domain}"
api_domain = "${domain}"
db_password = "${password}"
cookie_secret = "${base64:32}"
redis_password = "${password}"

[config]
[[config.mounts]]
filePath = "clickhouse/clickhouse-config.xml"
content = """
    <clickhouse>
        <logger>
            <level>warning</level>
            <console>true</console>
        </logger>
        <keep_alive_timeout>10</keep_alive_timeout>
        <!-- Stop all the unnecessary logging -->
        <query_thread_log remove="remove"/>
        <query_log remove="remove"/>
        <text_log remove="remove"/>
        <trace_log remove="remove"/>
        <metric_log remove="remove"/>
        <asynchronous_metric_log remove="remove"/>
        <session_log remove="remove"/>
        <part_log remove="remove"/>
        <listen_host>0.0.0.0</listen_host>
        <interserver_listen_host>0.0.0.0</interserver_listen_host>
        <interserver_http_host>opch</interserver_http_host>
        <!-- Disable cgroup memory observer -->
        <cgroups_memory_usage_observer_wait_time>0</cgroups_memory_usage_observer_wait_time>
        <!-- Not used anymore, but kept for backwards compatibility -->
        <macros>
            <shard>1</shard>
            <replica>replica1</replica>
            <cluster>openpanel_cluster</cluster>
        </macros>
    </clickhouse>
"""

[[config.mounts]]
filePath = "clickhouse/clickhouse-user-config.xml"
content = """
    <clickhouse>
        <profiles>
        <default>
            <log_queries>0</log_queries>
            <log_query_threads>0</log_query_threads>
        </default>
    </profiles>
    </clickhouse>
"""

[[config.mounts]]
filePath = "clickhouse/init-db.sql"
content = """
CREATE DATABASE IF NOT EXISTS openpanel;
"""

[[config.domains]]
serviceName = "op-dashboard"
port = 3_000
host = "${main_domain}"

[[config.domains]]
serviceName = "op-api"
port = 3_000
host = "${api_domain}"

[config.env]
SERVICE_FQDN_OPDASHBOARD = "http://${main_domain}"
SERVICE_FQDN_OPAPI = "http://${api_domain}"
OPENPANEL_POSTGRES_DB = "openpanel-db"
SERVICE_USER_POSTGRES = "openpanel"
SERVICE_PASSWORD_POSTGRES = "${db_password}"
SERVICE_PASSWORD_REDIS = "${redis_password}"
SERVICE_BASE64_COOKIESECRET = "${cookie_secret}"
OP_WORKER_REPLICAS = "1"

RESEND_API_KEY = ""
OPENPANEL_ALLOW_REGISTRATION = "true"
OPENPANEL_ALLOW_INVITATION = "true"
''',
)
