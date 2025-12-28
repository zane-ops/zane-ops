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
