"""
Docker Compose test fixtures representing real-world use cases.
"""

# Simple single database service
DOCKER_COMPOSE_SIMPLE_DB = """
services:
  db:
    image: postgres:18-alpine
    environment:
      POSTGRES_PASSWORD: supersecret
      POSTGRES_DB: myapp
    volumes:
      - db_data:/var/lib/postgresql

volumes:
  db_data:
"""

# Simple web service with HTTP exposure
DOCKER_COMPOSE_WEB_SERVICE = """
services:
  web:
    image: nginx:latest
    deploy:
      labels:
        zane.expose: "true"
        zane.http.port: "80"
        zane.http.routes.0.domain: "example.com"
        zane.http.routes.0.base_path: "/"
"""

# WordPress with MySQL
DOCKER_COMPOSE_WORDPRESS = """
services:
  wordpress:
    image: wordpress:latest
    environment:
      WORDPRESS_DB_HOST: db
      WORDPRESS_DB_USER: wpuser
      WORDPRESS_DB_PASSWORD: wppass
      WORDPRESS_DB_NAME: wordpress
    volumes:
      - wordpress_data:/var/www/html
    deploy:
      labels:
        zane.expose: "true"
        zane.http.port: "80"
        zane.http.routes.0.domain: "myblog.example.com"
        zane.http.routes.0.base_path: "/"

  db:
    image: mysql:8
    environment:
      MYSQL_ROOT_PASSWORD: rootpass
      MYSQL_DATABASE: wordpress
      MYSQL_USER: wpuser
      MYSQL_PASSWORD: wppass
    volumes:
      - db_data:/var/lib/mysql

volumes:
  wordpress_data:
  db_data:
"""

# Node.js API with Redis and PostgreSQL
DOCKER_COMPOSE_NODEJS_API = """
services:
  api:
    image: node:20-alpine
    command: npm start
    environment:
      DATABASE_URL: postgres://user:pass@db:5432/mydb
      REDIS_URL: redis://cache:6379
      NODE_ENV: production
    depends_on:
      - db
      - cache
    deploy:
      labels:
        zane.expose: "true"
        zane.http.port: "3000"
        zane.http.routes.0.domain: "api.example.com"
        zane.http.routes.0.base_path: "/"

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_PASSWORD: secret
      POSTGRES_DB: mydb
    volumes:
      - postgres_data:/var/lib/postgresql/data

  cache:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
"""

# Service with multiple HTTP routes
DOCKER_COMPOSE_MULTIPLE_ROUTES = """
services:
  api:
    image: myapi:latest
    deploy:
      labels:
        zane.expose: "true"
        zane.http.port: "3000"
        zane.http.routes.0.domain: "api.example.com"
        zane.http.routes.0.base_path: "/"
        zane.http.routes.0.strip_prefix: "false"
        zane.http.routes.1.domain: "example.com"
        zane.http.routes.1.base_path: "/api"
        zane.http.routes.1.strip_prefix: "true"
"""

# Admin panel with HTTP Basic Auth
DOCKER_COMPOSE_WITH_AUTH = """
services:
  admin:
    image: phpmyadmin:latest
    environment:
      PMA_HOST: db
    deploy:
      labels:
        zane.expose: "true"
        zane.http.port: "80"
        zane.http.routes.0.domain: "admin.example.com"
        zane.http.routes.0.base_path: "/"
        zane.http.routes.0.auth_enabled: "true"
        zane.http.routes.0.auth_user: "admin"
        zane.http.routes.0.auth_password: "supersecret"

  db:
    image: mariadb:11
    environment:
      MYSQL_ROOT_PASSWORD: rootpass
    volumes:
      - db_data:/var/lib/mysql

volumes:
  db_data:
"""

# Service with deploy configuration and resource limits
DOCKER_COMPOSE_WITH_RESOURCES = """
services:
  app:
    image: myapp:latest
    deploy:
      replicas: 3
      update_config:
        parallelism: 1
        delay: 10s
        order: start-first
        failure_action: rollback
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
        reservations:
          cpus: '0.25'
          memory: 256M
      labels:
        zane.expose: "true"
        zane.http.port: "8000"
        zane.http.routes.0.domain: "app.example.com"
        zane.http.routes.0.base_path: "/"
"""

# Nginx reverse proxy with upstream services
DOCKER_COMPOSE_NGINX_PROXY = """
services:
  proxy:
    image: nginx:alpine
    depends_on:
      - app
    deploy:
      labels:
        zane.expose: "true"
        zane.http.port: "80"
        zane.http.routes.0.domain: "example.com"
        zane.http.routes.0.base_path: "/"

  app:
    image: myapp:latest
    environment:
      PORT: 8080
"""

# Django app with PostgreSQL and Celery
DOCKER_COMPOSE_DJANGO = """
services:
  web:
    image: mydjango:latest
    command: gunicorn myproject.wsgi:application --bind 0.0.0.0:8000
    environment:
      DATABASE_URL: postgres://django:secret@db:5432/djangodb
      REDIS_URL: redis://redis:6379
    depends_on:
      - db
      - redis
    deploy:
      labels:
        zane.expose: "true"
        zane.http.port: "8000"
        zane.http.routes.0.domain: "myapp.example.com"
        zane.http.routes.0.base_path: "/"

  worker:
    image: mydjango:latest
    command: celery -A myproject worker -l info
    environment:
      DATABASE_URL: postgres://django:secret@db:5432/djangodb
      REDIS_URL: redis://redis:6379
    depends_on:
      - db
      - redis

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: djangodb
      POSTGRES_USER: django
      POSTGRES_PASSWORD: secret
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine

volumes:
  postgres_data:
"""

# Service with external volume reference
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

# Service without zane network (should be auto-injected)
DOCKER_COMPOSE_NO_NETWORKS = """
services:
  app:
    image: nginx:alpine
    deploy:
      labels:
        zane.expose: "true"
        zane.http.port: "80"
        zane.http.routes.0.domain: "example.com"
        zane.http.routes.0.base_path: "/"
"""

# Service with Docker secrets
DOCKER_COMPOSE_WITH_SECRETS = """
services:
  app:
    image: myapp:latest
    secrets:
      - db_password
      - api_key
    environment:
      DB_PASSWORD_FILE: /run/secrets/db_password
      API_KEY_FILE: /run/secrets/api_key
    deploy:
      labels:
        zane.expose: "true"
        zane.http.port: "3000"
        zane.http.routes.0.domain: "app.example.com"
        zane.http.routes.0.base_path: "/"

secrets:
  db_password:
    external: true
  api_key:
    external: true
"""

# Service with Docker configs
DOCKER_COMPOSE_WITH_CONFIGS = """
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
        zane.expose: "true"
        zane.http.port: "80"
        zane.http.routes.0.domain: "example.com"
        zane.http.routes.0.base_path: "/"

configs:
  nginx_config:
    external: true
  site_config:
    external: true
"""

# Service with both secrets and configs
DOCKER_COMPOSE_WITH_SECRETS_AND_CONFIGS = """
services:
  app:
    image: myapp:latest
    secrets:
      - db_password
    configs:
      - source: app_config
        target: /app/config.yml
    environment:
      DB_PASSWORD_FILE: /run/secrets/db_password
      CONFIG_FILE: /app/config.yml

secrets:
  db_password:
    external: true

configs:
  app_config:
    external: true
"""

# INVALID: Service with build context (not supported for stacks)
DOCKER_COMPOSE_INVALID_BUILD = """
services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
"""

# INVALID: Service without image and without build
DOCKER_COMPOSE_INVALID_NO_IMAGE = """
services:
  app:
    command: echo "Hello World"
"""

# INVALID: Invalid service name (starts with digit)
DOCKER_COMPOSE_INVALID_SERVICE_NAME_DIGIT = """
services:
  1app:
    image: myapp:latest
"""

# INVALID: Invalid service name (uppercase)
DOCKER_COMPOSE_INVALID_SERVICE_NAME_UPPERCASE = """
services:
  MyApp:
    image: myapp:latest
"""

# INVALID: Invalid service name (special characters)
DOCKER_COMPOSE_INVALID_SERVICE_NAME_SPECIAL = """
services:
  my@app:
    image: myapp:latest
"""

# INVALID: Invalid YAML syntax
DOCKER_COMPOSE_INVALID_YAML = """
services:
  app:
    image: myapp:latest
  environment:
    NODE_ENV: production
"""

# INVALID: Empty file
DOCKER_COMPOSE_INVALID_EMPTY = ""

# INVALID: No services defined
DOCKER_COMPOSE_INVALID_NO_SERVICES = """
networks:
  default:
"""

# INVALID: Services is not a dictionary
DOCKER_COMPOSE_INVALID_SERVICES_NOT_DICT = """
services:
  - app
  - db
"""

# Minimal valid compose
DOCKER_COMPOSE_MINIMAL = """
services:
  app:
    image: nginx:alpine
"""

# Comprehensive stack with fields requiring reconciliation
# Tests: volumes, ports, depends_on, healthcheck, configs, restart, user, working_dir, etc.
DOCKER_COMPOSE_COMPREHENSIVE = """
services:
  frontend:
    image: node:20-alpine
    command: npm run start
    working_dir: /app
    user: "1000:1000"
    ports:
      - "3000:3000"
      - "3001:3001"
    volumes:
      - app_data:/app/data
      - ./config:/app/config:ro
      - /var/log/app:/var/log/app
    depends_on:
      api:
        condition: service_healthy
      cache:
        condition: service_started
    environment:
      NODE_ENV: production
      API_URL: http://api:8000
      REDIS_URL: redis://cache:6379
    healthcheck:
      test: ["CMD", "node", "healthcheck.js"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    restart: unless-stopped
    deploy:
      replicas: 2
      labels:
        zane.expose: "true"
        zane.http.port: "3000"
        zane.http.routes.0.domain: "app.example.com"
        zane.http.routes.0.base_path: "/"

  api:
    image: python:3.12-slim
    command: uvicorn main:app --host 0.0.0.0 --port 8000
    working_dir: /code
    ports:
      - "8000:8000"
    volumes:
      - api_data:/data
      - ./app:/code:ro
    depends_on:
      - db
      - cache
    environment:
      DATABASE_URL: postgresql://user:pass@db:5432/appdb
      REDIS_URL: redis://cache:6379
      SECRET_KEY: change-me-in-production
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: on-failure
    deploy:
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
      resources:
        limits:
          cpus: '1.0'
          memory: 1024M
        reservations:
          cpus: '0.5'
          memory: 512M

  db:
    image: postgres:16-alpine
    volumes:
      - db_data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    environment:
      POSTGRES_DB: appdb
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U user -d appdb"]
      interval: 5s
      timeout: 3s
      retries: 10
      start_period: 10s
    restart: always
    deploy:
      placement:
        constraints:
          - node.labels.database == true
    shm_size: 128mb

  cache:
    image: redis:7-alpine
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru
    volumes:
      - cache_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
    restart: always

  worker:
    image: python:3.12-slim
    command: celery -A tasks worker --loglevel=info
    working_dir: /code
    volumes:
      - worker_logs:/var/log/celery
      - ./app:/code:ro
    depends_on:
      - db
      - cache
    environment:
      DATABASE_URL: postgresql://user:pass@db:5432/appdb
      REDIS_URL: redis://cache:6379
      CELERY_BROKER_URL: redis://cache:6379/0
      CELERY_RESULT_BACKEND: redis://cache:6379/1
    restart: on-failure
    deploy:
      replicas: 3
      mode: replicated
      update_config:
        parallelism: 1
        delay: 10s
        order: stop-first

volumes:
  app_data:
    driver: local
    driver_opts:
      type: none
      device: /mnt/app_data
      o: bind
  api_data:
  db_data:
    driver: local
    labels:
      backup: "daily"
      retention: "30d"
  cache_data:
  worker_logs:

networks:
  default:
    driver: overlay
    attachable: true
"""

# DOCKER_COMPOSE_PENPOT = """
# ## Common flags:
# # demo-users
# # email-verification
# # log-emails
# # log-invitation-tokens
# # login-with-github
# # login-with-gitlab
# # login-with-google
# # login-with-ldap
# # login-with-oidc
# # login-with-password
# # prepl-server
# # registration
# # secure-session-cookies
# # smtp
# # smtp-debug
# # telemetry
# # webhooks
# ##
# ## You can read more about all available flags and other
# ## environment variables here:
# ## https://help.penpot.app/technical-guide/configuration/#penpot-configuration
# #
# # WARNING: if you're exposing Penpot to the internet, you should remove the flags
# # 'disable-secure-session-cookies' and 'disable-email-verification'
# x-flags: &penpot-flags
#   PENPOT_FLAGS: disable-email-verification enable-smtp enable-prepl-server disable-secure-session-cookies

# x-uri: &penpot-public-uri
#   PENPOT_PUBLIC_URI: http://localhost:9001

# x-body-size: &penpot-http-body-size
#   # Max body size (30MiB); Used for plain requests, should never be
#   # greater than multi-part size
#   PENPOT_HTTP_SERVER_MAX_BODY_SIZE: 31457280

#   # Max multipart body size (350MiB)
#   PENPOT_HTTP_SERVER_MAX_MULTIPART_BODY_SIZE: 367001600

# ## Penpot SECRET KEY. It serves as a master key from which other keys for subsystems
# ## (eg http sessions, or invitations) are derived.
# ##
# ## We recommend to use a trully randomly generated
# ## 512 bits base64 encoded string here. You can generate one with:
# ##
# ## python3 -c "import secrets; print(secrets.token_urlsafe(64))"
# x-secret-key: &penpot-secret-key
#   PENPOT_SECRET_KEY: change-this-insecure-key

# networks:
#   penpot:

# volumes:
#   penpot_postgres_v15:
#   penpot_assets:
#   # penpot_traefik:

# services:
#   ## Traefik service declaration example. Consider using it if you are going to expose
#   ## penpot to the internet, or a different host than `localhost`.

#   # traefik:
#   #   image: traefik:v3.3
#   #   networks:
#   #     - penpot
#   #   command:
#   #     - "--api.insecure=true"
#   #     - "--entryPoints.web.address=:80"
#   #     - "--providers.docker=true"
#   #     - "--providers.docker.exposedbydefault=false"
#   #     - "--entryPoints.websecure.address=:443"
#   #     - "--certificatesresolvers.letsencrypt.acme.tlschallenge=true"
#   #     - "--certificatesresolvers.letsencrypt.acme.email=<EMAIL_ADDRESS>"
#   #     - "--certificatesresolvers.letsencrypt.acme.storage=/traefik/acme.json"
#   #   volumes:
#   #     - "penpot_traefik:/traefik"
#   #     - "/var/run/docker.sock:/var/run/docker.sock"
#   #   ports:
#   #     - "80:80"
#   #     - "443:443"

#   penpot-frontend:
#     image: "penpotapp/frontend:${PENPOT_VERSION:-latest}"
#     restart: always
#     ports:
#       - 9001:8080

#     volumes:
#       - penpot_assets:/opt/data/assets

#     depends_on:
#       - penpot-backend
#       - penpot-exporter

#     networks:
#       - penpot

#     # labels:
#       # - "traefik.enable=true"

#       # ## HTTPS: example of labels for the case where penpot will be exposed to the
#       # ## internet with HTTPS using traefik.

#       # - "traefik.http.routers.penpot-https.rule=Host(`<DOMAIN_NAME>`)"
#       # - "traefik.http.routers.penpot-https.entrypoints=websecure"
#       # - "traefik.http.routers.penpot-https.tls.certresolver=letsencrypt"
#       # - "traefik.http.routers.penpot-https.tls=true"

#     environment:
#       << : [*penpot-flags, *penpot-http-body-size]

#   penpot-backend:
#     image: "penpotapp/backend:${PENPOT_VERSION:-latest}"
#     restart: always

#     volumes:
#       - penpot_assets:/opt/data/assets

#     depends_on:
#       penpot-postgres:
#         condition: service_healthy
#       penpot-valkey:
#         condition: service_healthy

#     networks:
#       - penpot

#     ## Configuration envronment variables for the backend container.

#     environment:
#       << : [*penpot-flags, *penpot-public-uri, *penpot-http-body-size, *penpot-secret-key]

#       ## The PREPL host. Mainly used for external programatic access to penpot backend
#       ## (example: admin). By default it will listen on `localhost` but if you are going to use
#       ## the `admin`, you will need to uncomment this and set the host to `0.0.0.0`.

#       # PENPOT_PREPL_HOST: 0.0.0.0

#       ## Database connection parameters. Don't touch them unless you are using custom
#       ## postgresql connection parameters.

#       PENPOT_DATABASE_URI: postgresql://penpot-postgres/penpot
#       PENPOT_DATABASE_USERNAME: penpot
#       PENPOT_DATABASE_PASSWORD: penpot

#       ## Valkey (or previously redis) is used for the websockets notifications. Don't touch
#       ## unless the valkey container has different parameters or different name.

#       PENPOT_REDIS_URI: redis://penpot-valkey/0

#       ## Default configuration for assets storage: using filesystem based with all files
#       ## stored in a docker volume.

#       PENPOT_ASSETS_STORAGE_BACKEND: assets-fs
#       PENPOT_STORAGE_ASSETS_FS_DIRECTORY: /opt/data/assets

#       ## Also can be configured to to use a S3 compatible storage.

#       # AWS_ACCESS_KEY_ID: <KEY_ID>
#       # AWS_SECRET_ACCESS_KEY: <ACCESS_KEY>
#       # PENPOT_ASSETS_STORAGE_BACKEND: assets-s3
#       # PENPOT_STORAGE_ASSETS_S3_ENDPOINT: <ENDPOINT>
#       # PENPOT_STORAGE_ASSETS_S3_BUCKET: <BUKET_NAME>

#       ## Telemetry. When enabled, a periodical process will send anonymous data about this
#       ## instance. Telemetry data will enable us to learn how the application is used,
#       ## based on real scenarios. If you want to help us, please leave it enabled. You can
#       ## audit what data we send with the code available on github.

#       PENPOT_TELEMETRY_ENABLED: true
#       PENPOT_TELEMETRY_REFERER: compose

#       ## Example SMTP/Email configuration. By default, emails are sent to the mailcatch
#       ## service, but for production usage it is recommended to setup a real SMTP
#       ## provider. Emails are used to confirm user registrations & invitations. Look below
#       ## how the mailcatch service is configured.

#       PENPOT_SMTP_DEFAULT_FROM: no-reply@example.com
#       PENPOT_SMTP_DEFAULT_REPLY_TO: no-reply@example.com
#       PENPOT_SMTP_HOST: penpot-mailcatch
#       PENPOT_SMTP_PORT: 1025
#       PENPOT_SMTP_USERNAME:
#       PENPOT_SMTP_PASSWORD:
#       PENPOT_SMTP_TLS: false
#       PENPOT_SMTP_SSL: false

#   penpot-exporter:
#     image: "penpotapp/exporter:${PENPOT_VERSION:-latest}"
#     restart: always

#     depends_on:
#       penpot-valkey:
#         condition: service_healthy

#     networks:
#       - penpot

#     environment:
#       << : [*penpot-secret-key]
#       # Don't touch it; this uses an internal docker network to
#       # communicate with the frontend.
#       PENPOT_PUBLIC_URI: http://penpot-frontend:8080

#       ## Valkey (or previously Redis) is used for the websockets notifications.
#       PENPOT_REDIS_URI: redis://penpot-valkey/0

#   penpot-postgres:
#     image: "postgres:15"
#     restart: always
#     stop_signal: SIGINT

#     healthcheck:
#       test: ["CMD-SHELL", "pg_isready -U penpot"]
#       interval: 2s
#       timeout: 10s
#       retries: 5
#       start_period: 2s

#     volumes:
#       - penpot_postgres_v15:/var/lib/postgresql/data

#     networks:
#       - penpot

#     environment:
#       - POSTGRES_INITDB_ARGS=--data-checksums
#       - POSTGRES_DB=penpot
#       - POSTGRES_USER=penpot
#       - POSTGRES_PASSWORD=penpot

#   penpot-valkey:
#     image: valkey/valkey:8.1
#     restart: always

#     healthcheck:
#       test: ["CMD-SHELL", "valkey-cli ping | grep PONG"]
#       interval: 1s
#       timeout: 3s
#       retries: 5
#       start_period: 3s

#     networks:
#       - penpot

#     environment:
#       # You can increase the max memory size if you have sufficient resources,
#       # although this should not be necessary.
#       - VALKEY_EXTRA_FLAGS=--maxmemory 128mb --maxmemory-policy volatile-lfu

#   ## A mailcatch service, used as temporal SMTP server. You can access via HTTP to the
#   ## port 1080 for read all emails the penpot platform has sent. Should be only used as a
#   ## temporal solution while no real SMTP provider is configured.

#   penpot-mailcatch:
#     image: sj26/mailcatcher:latest
#     restart: always
#     expose:
#       - '1025'
#     ports:
#       - "1080:1080"
#     networks:
#       - penpot

# """
