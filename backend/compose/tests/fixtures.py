"""
Docker Compose test fixtures representing real-world use cases.
"""

DOCKER_COMPOSE_WITH_PLACEHOLDERS = """
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: {{ generate_user }}
      POSTGRES_PASSWORD: {{ generate_secure_password }}
      POSTGRES_DB: {{ generate_random_slug }}
  app:
    image: myapp:latest
    environment:
      API_TOKEN: {{ generate_random_chars_32 }}
      SECRET_KEY: {{ generate_random_chars_64 }}
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
    environment:
      DATABASE_URL: postgresql://postgres:secret@db:5432/myapp
      REDIS_URL: redis://cache:6379
    deploy:
      labels:
        zane.http.port: "8000"
        zane.http.routes.0.domain: "example.com"
        zane.http.routes.0.base_path: "/"

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_PASSWORD: secret
      POSTGRES_DB: myapp

  cache:
    image: redis:7-alpine
"""


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
        zane.http.port: "8000"
        zane.http.routes.0.domain: "app.example.com"
        zane.http.routes.0.base_path: "/"
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

DOCKER_COMPOSE_NO_NETWORKS = """
services:
  app:
    image: nginx:alpine
    deploy:
      labels:
        zane.http.port: "80"
        zane.http.routes.0.domain: "example.com"
        zane.http.routes.0.base_path: "/"
"""

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
        zane.http.port: "3000"
        zane.http.routes.0.domain: "app.example.com"
        zane.http.routes.0.base_path: "/"

secrets:
  db_password:
    external: true
  api_key:
    external: true
"""

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
        zane.http.port: "80"
        zane.http.routes.0.domain: "example.com"
        zane.http.routes.0.base_path: "/"

configs:
  nginx_config:
    external: true
  site_config:
    external: true
"""

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

DOCKER_COMPOSE_MINIMAL = """
services:
  app:
    image: nginx:alpine
"""

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
      - api
      - cache
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

INVALID_COMPOSE_WITH_BUILD = """
services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
"""

INVALID_COMPOSE_NO_IMAGE = """
services:
  app:
    command: echo "Hello World"
"""

INVALID_COMPOSE_SERVICE_NAME_DIGIT = """
services:
  1app:
    image: myapp:latest
"""

INVALID_COMPOSE_SERVICE_NAME_UPPERCASE = """
services:
  MyApp:
    image: myapp:latest
"""

INVALID_COMPOSE_RELATIVE_BIND_VOLUME = """
services:
  MyApp:
    image: postgres:alpine
    volumes:
      - ./db-data:/var/lib/postgresql
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

INVALID_COMPOSE_SERVICES_NOT_DICT = """
services:
  - app
  - db
"""
