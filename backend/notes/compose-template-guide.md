# ZaneOps Docker Compose Template Guide

## Table of Contents

1. [Introduction](#introduction)
2. [Basic Structure](#basic-structure)
3. [Deployment Process](#deployment-process)
4. [Template Expressions (`x-zane-env`)](#template-expressions-x-zane-env)
5. [Service Configuration](#service-configuration)
6. [Routing and URL Configuration](#routing-and-url-configuration)
7. [Volumes](#volumes)
8. [Docker Configs](#docker-configs)
9. [Networks](#networks)
10. [Environment Variables](#environment-variables)
11. [Service Dependencies](#service-dependencies)
12. [Complete Examples](#complete-examples)
13. [Dokploy Template Migration](#dokploy-template-migration)
14. [Advanced Patterns](#advanced-patterns)
15. [Troubleshooting](#troubleshooting)

---

## Introduction

ZaneOps extends standard Docker Compose syntax with template expressions and automatic service orchestration. This guide covers everything you need to create production-ready compose templates for ZaneOps.

### What Makes ZaneOps Compose Different?

- **Template expressions** for generating secrets, domains, and service aliases
- **Label-based routing** for automatic HTTP/HTTPS configuration
- **Automatic service name hashing** to prevent DNS collisions
- **Three-tier networking** for service isolation and communication
- **Config versioning** for inline configuration files
- **Variable interpolation** using `${VAR}` syntax in env vars and configs

### Key Concepts

- **Stack**: A docker-compose file containing one or more services
- **Template expressions**: Jinja2-like syntax in `x-zane-env` for generating values
- **Service hashing**: All service names prefixed with `{hash_prefix}_` to prevent DNS collisions
- **Lazy computation**: Templates processed only during deployment, not on save
- **Deployment method**: Stacks are deployed using `docker stack deploy --with-registry-auth` for automatic registry authentication

---

## Basic Structure

### Minimal Template

```yaml
services:
  app:
    image: nginx:latest
```

This is the simplest valid ZaneOps compose template. ZaneOps will:
1. Hash the service name: `app` → `abc123_app` (where `abc123` is the stack's hash prefix)
2. Inject the `zane` network for inter-service communication
3. Deploy using `docker stack deploy --with-registry-auth` for automatic registry authentication
4. Create the service as a Docker Swarm service

### Complete Template Structure

```yaml
# Optional: Docker Compose version (ignored by ZaneOps)
version: "3.8"

# ZaneOps template expressions (optional but recommended)
x-zane-env:
  # Define stack-wide variables with template expressions
  VAR_NAME: "{{ template_expression }}"

# Services definition (required)
services:
  service_name:
    image: image:tag
    environment:
      KEY: ${VALUE}
    deploy:
      labels:
        # Routing configuration
        zane.http.routes.0.domain: "example.com"

# Optional: Named volumes
volumes:
  data:

# Optional: Custom networks (ZaneOps injects 'zane' network automatically)
networks:
  backend:

# Optional: Inline configs
configs:
  nginx_config:
    content: |
      server {
        listen 80;
      }
```

---

## Deployment Process

### How ZaneOps Deploys Stacks

ZaneOps uses Docker Swarm's stack deployment mechanism with automatic registry authentication:

```bash
docker stack deploy --with-registry-auth --compose-file <processed-compose.yml> <stack-name>
```

**Key deployment steps**:

1. **Template processing**: `x-zane-env` expressions evaluated, variables expanded
2. **Service name hashing**: All service names prefixed with stack's hash prefix
3. **Network injection**: `zane` network added to all services
4. **Config creation**: Inline configs created as versioned Docker configs
5. **Stack deployment**: `docker stack deploy --with-registry-auth` executed

### The `--with-registry-auth` Flag

This flag automatically shares registry credentials with Docker Swarm workers, enabling:

- **Private registry support**: Pull images from authenticated registries (DockerHub, GHCR, private registries)
- **Automatic credential propagation**: No manual registry login needed on worker nodes
- **Secure credential handling**: Credentials stored in Docker Swarm's encrypted storage

**Example use cases**:
- Private images from DockerHub: `myorg/private-app:latest`
- GitHub Container Registry: `ghcr.io/myorg/app:latest`
- Self-hosted registries: `registry.company.com/app:latest`

### Registry Authentication Setup

To use private images, configure registry credentials in ZaneOps:

1. **Via UI**: Settings → Container Registry → Add Registry
2. **Via API**:
   ```http
   POST /api/container-registries/
   Content-Type: application/json

   {
     "url": "https://index.docker.io/v1/",
     "username": "myuser",
     "password": "mytoken"
   }
   ```

Once configured, ZaneOps automatically uses these credentials during `docker stack deploy`.

---

## Template Expressions (`x-zane-env`)

The `x-zane-env` section defines stack-wide environment variables using template expressions. These expressions are evaluated **once during first deployment** and values are persisted.

### Syntax

```yaml
x-zane-env:
  VARIABLE_NAME: "{{ template_function }}"
  ANOTHER_VAR: "{{ template_function | argument }}"
```

**Important**: Variables defined in `x-zane-env` must be referenced using `${VAR_NAME}` syntax (with curly braces) to be interpolated in services, configs, and other parts of the compose file. Without the braces, the variable will not be expanded.

### Available Template Functions

#### 1. `generate_username`

Generates a random username in the format `{adjective}{animal}{number}`.

```yaml
x-zane-env:
  DB_USER: "{{ generate_username }}"
```

**Output example**: `reddog65`, `bluecat42`, `happylion91`

---

#### 2. `generate_password | <length>`

Generates a cryptographically secure random password as a hexadecimal string.

**Requirements**:
- Length must be even (divisible by 2)
- Minimum length: 8

```yaml
x-zane-env:
  DB_PASSWORD: "{{ generate_password | 32 }}"
  API_SECRET: "{{ generate_password | 64 }}"
  SHORT_TOKEN: "{{ generate_password | 16 }}"
```

**Output example**:
- `32` → `a1b2c3d4e5f6789012345678abcdef01`
- `64` → `a1b2c3d4e5f6789012345678abcdef01a1b2c3d4e5f6789012345678abcdef01`

**Common mistakes**:
```yaml
# ❌ WRONG - odd length
PASSWORD: "{{ generate_password | 31 }}"

# ❌ WRONG - too short
PASSWORD: "{{ generate_password | 4 }}"

# ✅ CORRECT
PASSWORD: "{{ generate_password | 32 }}"
```

---

#### 3. `generate_slug`

Generates a URL-friendly slug in the format `{adjective}-{noun}-{number}`.

```yaml
x-zane-env:
  DB_NAME: "{{ generate_slug }}"
  BUCKET_NAME: "{{ generate_slug }}"
```

**Output example**: `happy-tree-91`, `brave-river-42`, `quick-mountain-17`

---

#### 4. `generate_domain`

Generates a unique domain for your stack in the format:
`{project_slug}-{stack_slug}-{random}.{ROOT_DOMAIN}`

```yaml
x-zane-env:
  APP_URL: "{{ generate_domain }}"
  CALLBACK_URL: "https://{{ generate_domain }}/auth/callback"
```

**Output example**:
- If project is `my-app`, stack is `backend`, and `ROOT_DOMAIN` is `zaneops.dev`:
  - `my-app-backend-a1b2c3.zaneops.dev`

**Note**: The random suffix ensures uniqueness across environments and prevents collisions.

---

#### 5. `generate_uuid`

Generates a UUID v4 (universally unique identifier).

```yaml
x-zane-env:
  LICENSE_ID: "{{ generate_uuid }}"
  INSTALLATION_ID: "{{ generate_uuid }}"
```

**Output example**: `550e8400-e29b-41d4-a716-446655440000`

---

#### 6. `generate_email`

Generates a fake but valid-looking email address.

```yaml
x-zane-env:
  ADMIN_EMAIL: "{{ generate_email }}"
  SUPPORT_EMAIL: "{{ generate_email }}"
```

**Output example**: `john.doe@example.com`, `admin@domain.local`

---

#### 7. `network_alias | 'service_name'`

Generates an environment-scoped network alias for inter-service communication within the same environment.

**Format**: `{network_alias_prefix}-{service_name}`

**Use case**: Services communicating within the same environment (e.g., all services in "production" or all services in "staging").

```yaml
x-zane-env:
  DB_HOST: "{{ network_alias | 'postgres' }}"
  REDIS_URL: "redis://{{ network_alias | 'redis' }}:6379"
```

**Output example**:
- If `network_alias_prefix` is `my-stack`:
  - `my-stack-postgres`
  - `my-stack-redis`

**Why use this?**
- Stable across deployments (doesn't change when stack is redeployed)
- Scoped to the environment - services in the same environment can communicate
- Preferred for most service-to-service communication

---

#### 8. `global_alias | 'service_name'`

Generates a globally unique network alias that is accessible across all of ZaneOps - across all projects and environments.

**Format**: `{hash_prefix}_{service_name}`

**Use case**: Cross-project or cross-environment communication.

```yaml
x-zane-env:
  GLOBAL_DB: "{{ global_alias | 'postgres' }}"
```

**Output example**:
- If stack hash is `abc123`:
  - `abc123_postgres`

**When to use**:
- Cross-project service references
- Cross-environment communication (e.g., staging service connecting to production database)
- Debugging and troubleshooting
- Most cases should use `network_alias` instead for environment isolation

---

### Variable Interpolation

All variables defined in `x-zane-env` can be referenced using `${VAR}` syntax:

```yaml
x-zane-env:
  DB_USER: "{{ generate_username }}"
  DB_PASSWORD: "{{ generate_password | 32 }}"
  DB_NAME: "{{ generate_slug }}"
  DB_HOST: "{{ network_alias | 'postgres' }}"
  DB_PORT: "5432"

  # Compose variables from other variables
  DATABASE_URL: "postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"

services:
  app:
    image: myapp:latest
    environment:
      # Reference the composed variable
      DATABASE_URL: ${DATABASE_URL}
```

**Interpolation rules**:
- Works in `x-zane-env` values
- Works in service `environment` sections
- Works in inline config `content`
- Evaluated during deployment
- Uses Python's `expandvars.expand()` for `${VAR}` expansion

---

### Value Persistence

**Important**: Template expressions are evaluated **once** during the first deployment. Generated values are saved as `ComposeStackEnvOverride` records and reused in subsequent deployments.

**Lifecycle**:
1. **First deployment**:
   - Template expressions evaluated
   - Values generated (e.g., passwords, UUIDs)
   - Saved as `ComposeStackEnvOverride` records

2. **Subsequent deployments**:
   - Existing override values reused
   - No regeneration (passwords stay the same)

3. **Manual override**:
   - Use the API to update env override values
   - Template expressions won't regenerate once overridden

**Example**:
```yaml
x-zane-env:
  DB_PASSWORD: "{{ generate_password | 32 }}"
```

- Deploy 1: Generates `a1b2c3d4...`
- Deploy 2: Reuses `a1b2c3d4...`
- Deploy 3: Reuses `a1b2c3d4...`

---

## Service Configuration

### Basic Service Definition

```yaml
services:
  app:
    image: node:20-alpine
    command: ["npm", "start"]
    working_dir: /app
    user: "1000:1000"
    environment:
      NODE_ENV: production
```

### Service Properties

#### Required Properties

- **`image`**: Docker image to use (required)

```yaml
services:
  app:
    image: nginx:1.25-alpine
```

#### Optional Properties

- **`command`**: Override default command

```yaml
services:
  app:
    image: node:20
    command: ["node", "server.js"]
```

- **`working_dir`**: Set working directory

```yaml
services:
  app:
    image: python:3.12
    working_dir: /app
```

- **`user`**: Run as specific user

```yaml
services:
  app:
    image: node:20
    user: "1000:1000"
```

- **`environment`**: Environment variables (see [Environment Variables](#environment-variables))

- **`volumes`**: Volume mounts (see [Volumes](#volumes))

- **`configs`**: Config file mounts (see [Docker Configs](#docker-configs))

- **`depends_on`**: Service dependencies (see [Service Dependencies](#service-dependencies))

- **`deploy`**: Deployment configuration (labels, replicas, resources)

---

### Deploy Configuration

The `deploy` section configures Docker Swarm deployment behavior and ZaneOps routing.

```yaml
services:
  app:
    image: myapp:latest
    deploy:
      replicas: 3
      labels:
        # ZaneOps routing labels (see Routing section)
        zane.http.routes.0.domain: "example.com"
      resources:
        limits:
          cpus: '2'
          memory: 1G
        reservations:
          cpus: '1'
          memory: 512M
      restart_policy:
        condition: on-failure
        max_attempts: 3
```

**Important properties**:
- **`replicas`**: Number of service replicas (default: 1)
  - Set to `0` to pause the service (status becomes `SLEEPING`)
- **`labels`**: Routing configuration (ZaneOps-specific, see [Routing](#routing-and-url-configuration))
- **`resources`**: CPU and memory limits
- **`restart_policy`**: How Docker Swarm handles failures

---

### Properties Ignored by ZaneOps

These standard Docker Compose properties are **removed/ignored** by ZaneOps:

- **`ports`**: ZaneOps uses label-based routing, not port mappings
- **`expose`**: Not needed for Docker Swarm services
- **`restart`**: Use `deploy.restart_policy` instead
- **`build`**: ZaneOps uses pre-built images only

```yaml
# ❌ These will be ignored/removed
services:
  app:
    image: myapp:latest
    ports:
      - "3000:3000"  # Removed - use deploy.labels for routing
    expose:
      - "3000"        # Removed - not needed
    restart: always   # Removed - use deploy.restart_policy
```

---

## Routing and URL Configuration

ZaneOps uses **label-based routing** instead of port mappings. Configure routes using `deploy.labels`.

### Basic Route

```yaml
services:
  web:
    image: nginx:alpine
    deploy:
      labels:
        zane.http.routes.0.domain: "example.com"
        zane.http.routes.0.port: "80"
        zane.http.routes.0.base_path: "/"
        zane.http.routes.0.strip_prefix: "false"
```

**Route index**: The number in `routes.0` is the route index. Start at `0` for the first route.

---

### Route Properties

#### Required Properties

- **`zane.http.routes.{N}.domain`**: Domain name for this route
- **`zane.http.routes.{N}.port`**: Container port to route to

#### Optional Properties

- **`zane.http.routes.{N}.base_path`**: Path prefix (default: `/`)
- **`zane.http.routes.{N}.strip_prefix`**: Whether to strip base_path before proxying (default: `true`).
  Setting it to `true` means if your `base_path` is `/api` and you receive a request to `/api/auth/login`, your 
  service will receive a request to `/auth/login`.

---

### Multiple Routes (Multiple Domains)

You can configure multiple routes for a single service using different indices:

```yaml
services:
  web:
    image: myapp:latest
    deploy:
      labels:
        # Route 0: Main domain
        zane.http.routes.0.domain: "example.com"
        zane.http.routes.0.port: "8080"
        zane.http.routes.0.base_path: "/"
        zane.http.routes.0.strip_prefix: "false"

        # Route 1: Alternative domain
        zane.http.routes.1.domain: "www.example.com"
        zane.http.routes.1.port: "8080"
        zane.http.routes.1.base_path: "/"
        zane.http.routes.1.strip_prefix: "false"

        # Route 2: API subdomain
        zane.http.routes.2.domain: "api.example.com"
        zane.http.routes.2.port: "3000"
        zane.http.routes.2.base_path: "/"
        zane.http.routes.2.strip_prefix: "false"
```

**Rules**:
- Indices must be sequential: `0, 1, 2, 3, ...`
- Each route can have a different port
- Each route can have different path settings

---

### Path-Based Routing

Route different paths to different ports or services:

```yaml
services:
  web:
    image: nginx:alpine
    deploy:
      labels:
        # Root path
        zane.http.routes.0.domain: "example.com"
        zane.http.routes.0.port: "80"
        zane.http.routes.0.base_path: "/"
        zane.http.routes.0.strip_prefix: "false"

        # API path
        zane.http.routes.1.domain: "example.com"
        zane.http.routes.1.port: "3000"
        zane.http.routes.1.base_path: "/api"
        zane.http.routes.1.strip_prefix: "true"
```

**How it works**:
- Request to `example.com/` → port 80
- Request to `example.com/api/users` → port 3000 (receives `/users` if strip_prefix=true)

---

### Using Template Expressions in Routes

```yaml
x-zane-env:
  APP_DOMAIN: "{{ generate_domain }}"

services:
  web:
    image: myapp:latest
    deploy:
      labels:
        zane.http.routes.0.domain: "${APP_DOMAIN}"
        zane.http.routes.0.port: "8080"
        zane.http.routes.0.base_path: "/"
        zane.http.routes.0.strip_prefix: "false"
```

**Result**: Domain is auto-generated and stable across deployments.

---

### Route Validation

ZaneOps validates routes during deployment:

**✅ Valid**:
```yaml
zane.http.routes.0.domain: "example.com"
zane.http.routes.0.port: "80"
```

**❌ Invalid**:
```yaml
# Missing domain
zane.http.routes.0.port: "80"

# Missing port
zane.http.routes.0.domain: "example.com"

# Invalid port
zane.http.routes.0.domain: "example.com"
zane.http.routes.0.port: "not-a-number"

# Invalid strip_prefix
zane.http.routes.0.domain: "example.com"
zane.http.routes.0.port: "80"
zane.http.routes.0.strip_prefix: "yes"  # Must be "true" or "false"
```

---

## Volumes

ZaneOps supports **named volumes**, **absolute path bind mounts**, and **external volumes**. Relative path bind mounts are **not supported** and will be rejected during validation.

### Named Volumes

Named volumes are managed by Docker and persist across deployments.

```yaml
services:
  db:
    image: postgres:16
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

**Properties**:
- Persists data across deployments
- Managed by Docker
- Can be backed up using Docker commands

**With driver options**:
```yaml
services:
  db:
    image: postgres:16
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /mnt/data/postgres
```

---

### Absolute Path Bind Mounts

Bind mounts with absolute paths are supported for mapping host directories into containers.

```yaml
services:
  web:
    image: nginx:alpine
    volumes:
      - /data/html:/usr/share/nginx/html:ro
      - /etc/myapp/nginx.conf:/etc/nginx/nginx.conf:ro
```

**Properties**:
- Must use absolute paths (starting with `/`)
- Useful for accessing host system files or shared storage
- Use `:ro` suffix for read-only mounts

---

### Relative Paths Not Supported

**Important**: ZaneOps does **not** support relative path bind mounts and will actively validate against them.

```yaml
# ❌ NOT SUPPORTED - will fail validation
services:
  web:
    image: nginx:alpine
    volumes:
      - ./html:/usr/share/nginx/html:ro
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ../data:/app/data
```

**Use inline configs instead** for configuration files:
```yaml
# ✅ Correct approach for config files
services:
  web:
    image: nginx:alpine
    configs:
      - source: nginx_config
        target: /etc/nginx/nginx.conf

configs:
  nginx_config:
    content: |
      server {
        listen 80;
      }
```

**Or use absolute paths**:
```yaml
# ✅ Correct approach for host directories/files
services:
  portainer:
    image: portainer/portainer-ce:latest
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
```

**Note**: The `../files/` path pattern is only handled by the [Dokploy Migration Adapter](#dokploy-template-migration) when converting Dokploy templates to ZaneOps format. It is not valid syntax for native ZaneOps templates.

---

### External Volumes

Reference volumes created outside the stack:

```yaml
services:
  app:
    image: myapp:latest
    volumes:
      - shared_data:/data

volumes:
  shared_data:
    external: true
    name: actual_volume_name
```

**Use case**: Share volumes between stacks.

---

### Volume Mount Syntax

```yaml
services:
  app:
    volumes:
      # Named volume
      - volume_name:/container/path

      # Named volume (read-only)
      - volume_name:/container/path:ro

      # Absolute path bind mount
      - /host/path:/container/path

      # Absolute path bind mount (read-only)
      - /host/path:/container/path:ro

      # Long syntax
      - type: volume
        source: volume_name
        target: /container/path
        read_only: false
```

**Note**: Relative path bind mounts (`./path:/container/path`) are not supported. Use absolute paths, named volumes, or inline configs instead.

---

## Docker Configs

Docker configs allow you to inject configuration files into containers without rebuilding images. ZaneOps supports **inline configs** with automatic versioning.

### Inline Configs

Define config file content directly in the compose file:

```yaml
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

      http {
        server {
          listen 80;
          location / {
            root /usr/share/nginx/html;
          }
        }
      }
```

**How it works**:
1. ZaneOps extracts `content` from config definition
2. Creates versioned config name: `nginx_config_v1`
3. If content changes in next deployment: `nginx_config_v2`
4. Old config versions cleaned up automatically

---

### Config with Variable Interpolation

Configs support `${VAR}` interpolation from `x-zane-env`:

```yaml
x-zane-env:
  DB_HOST: "{{ network_alias | 'postgres' }}"
  DB_PORT: "5432"
  DB_NAME: "{{ generate_slug }}"

services:
  app:
    image: myapp:latest
    configs:
      - source: app_config
        target: /app/config.json

configs:
  app_config:
    content: |
      {
        "database": {
          "host": "${DB_HOST}",
          "port": ${DB_PORT},
          "name": "${DB_NAME}"
        }
      }
```

**Result**: Variables expanded before creating Docker config.

---

### Multiple Configs

```yaml
services:
  web:
    image: nginx:alpine
    configs:
      - source: nginx_conf
        target: /etc/nginx/nginx.conf
      - source: site_conf
        target: /etc/nginx/conf.d/default.conf
      - source: ssl_cert
        target: /etc/ssl/certs/cert.pem

configs:
  nginx_conf:
    content: |
      user nginx;
      worker_processes auto;

  site_conf:
    content: |
      server {
        listen 80;
        server_name example.com;
      }

  ssl_cert:
    content: |
      -----BEGIN CERTIFICATE-----
      ...
      -----END CERTIFICATE-----
```

---

### Config Versioning Details

**How versioning works**:
1. First deployment with inline config:
   - Config name: `nginx_config_v1`
   - Stored in `ComposeStack.configs` as:
     ```json
     {
       "nginx_config": {
         "content": "...",
         "version": 1
       }
     }
     ```

2. Second deployment with **same content**:
   - Config name: `nginx_config_v1` (reused)
   - Version stays at `1`

3. Third deployment with **different content**:
   - Config name: `nginx_config_v2` (new version)
   - Version increments to `2`
   - Old `nginx_config_v1` marked for cleanup

**Why versioning?**
- Docker configs are immutable (can't update existing config)
- Versioning allows updates without manual config management
- Old versions cleaned up automatically

---

## Networks

ZaneOps automatically manages networking for your services. Understanding the network architecture helps you configure service communication correctly.

### Automatic Network Injection

**All services automatically get**:
1. **`zane` network** (global overlay network)
   - Connects all ZaneOps services across all stacks
   - Used for ZaneOps internal communication (proxy, monitoring)

2. **Environment network** (e.g., `zn-env-abc123`)
   - Scoped to your environment (production, staging, etc.)
   - Used for services in the same environment to communicate

3. **Stack default network** (e.g., `zn-compose_stk_xyz789_default`)
   - Scoped to your stack
   - Used for inter-service communication within the stack

---

### Service Name Hashing and DNS

To prevent DNS collisions, ZaneOps hashes all service names:

**Original compose**:
```yaml
services:
  app:
    image: myapp:latest
  postgres:
    image: postgres:16
```

**After processing**:
- Service names become: `abc123_app`, `abc123_postgres`
- Where `abc123` is the stack's unique hash prefix

**DNS Resolution**:

In the **`zane` network**:
- `abc123_app.zaneops.internal`
- `abc123_postgres.zaneops.internal`

In the **environment network**:
- `{network_alias_prefix}-app` (e.g., `my-stack-app`)
- `{network_alias_prefix}-postgres` (e.g., `my-stack-postgres`)

In the **stack default network**:
- `app` (original name, for convenience)
- `postgres` (original name, for convenience)

---

### Service Communication Examples

**Within the same stack** (preferred):
```yaml
x-zane-env:
  DB_HOST: "{{ network_alias | 'postgres' }}"

services:
  app:
    image: myapp:latest
    environment:
      DATABASE_HOST: ${DB_HOST}

  postgres:
    image: postgres:16
```

**Result**: App connects to `my-stack-postgres` (environment network alias).

---

**Using default network** (also works):
```yaml
services:
  app:
    image: myapp:latest
    environment:
      # Reference by original service name
      DATABASE_HOST: postgres

  postgres:
    image: postgres:16
```

**Result**: App connects to `postgres` (resolves to `abc123_postgres` in stack default network).

---

**Cross-stack communication** (advanced):
```yaml
x-zane-env:
  SHARED_DB: "{{ global_alias | 'postgres' }}"

services:
  app:
    image: myapp:latest
    environment:
      # Connect to postgres from another stack
      DATABASE_HOST: ${SHARED_DB}
```

**Result**: App connects to `xyz789_postgres` (global alias from another stack's postgres).

---

### Custom Networks

You can define custom networks, but it's rarely needed:

```yaml
services:
  frontend:
    image: frontend:latest
    networks:
      - frontend
      - backend

  backend:
    image: backend:latest
    networks:
      - backend

  db:
    image: postgres:16
    networks:
      - backend

networks:
  frontend:
  backend:
```

**Notes**:
- Custom networks are **in addition to** the automatic `zane`, environment, and default networks
- Use custom networks for advanced isolation scenarios
- Most stacks don't need custom networks

---

## Environment Variables

### Service-Level Environment Variables

```yaml
services:
  app:
    image: myapp:latest
    environment:
      NODE_ENV: production
      PORT: "3000"
      API_KEY: "secret"
```

**Alternative syntax** (list format):
```yaml
services:
  app:
    image: myapp:latest
    environment:
      - NODE_ENV=production
      - PORT=3000
```

---

### Using `x-zane-env` Variables

Reference variables defined in `x-zane-env` using `${VAR}` syntax:

```yaml
x-zane-env:
  DB_USER: "{{ generate_username }}"
  DB_PASSWORD: "{{ generate_password | 32 }}"
  DB_HOST: "{{ network_alias | 'postgres' }}"

services:
  app:
    image: myapp:latest
    environment:
      DATABASE_USER: ${DB_USER}
      DATABASE_PASSWORD: ${DB_PASSWORD}
      DATABASE_HOST: ${DB_HOST}
```

---

### Variable Composition

Compose complex values from multiple variables:

```yaml
x-zane-env:
  DB_USER: "{{ generate_username }}"
  DB_PASSWORD: "{{ generate_password | 32 }}"
  DB_NAME: "{{ generate_slug }}"
  DB_HOST: "{{ network_alias | 'postgres' }}"
  DB_PORT: "5432"

  # Compose connection string
  DATABASE_URL: "postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"

services:
  app:
    image: myapp:latest
    environment:
      DATABASE_URL: ${DATABASE_URL}
```

---


## Service Dependencies

Use `depends_on` to control service startup order:

```yaml
services:
  app:
    image: myapp:latest
    depends_on:
      - postgres
      - redis

  postgres:
    image: postgres:16

  redis:
    image: redis:alpine
```

**Important notes**:
- ZaneOps converts `depends_on` dict format to list format
- Docker Swarm only uses this for initial startup order
- Does **not** wait for service to be "ready" (just started)
- Does **not** affect deployment order (all services deployed in parallel)

**Dict format** (Docker Compose v3.8+):
```yaml
services:
  app:
    depends_on:
      postgres:
        condition: service_healthy
```

**Converted to list** (Docker Swarm compatible):
```yaml
services:
  app:
    depends_on:
      - postgres
```

---

## Complete Examples

### Example 1: Simple Web App

```yaml
services:
  web:
    image: nginx:alpine
    deploy:
      replicas: 2
      labels:
        zane.http.routes.0.domain: "myapp.com"
        zane.http.routes.0.port: "80"
        zane.http.routes.0.base_path: "/"
        zane.http.routes.0.strip_prefix: "false"
```

---

### Example 2: Full Stack App (Frontend + Backend + Database)

```yaml
x-zane-env:
  # Database credentials
  DB_USER: "{{ generate_username }}"
  DB_PASSWORD: "{{ generate_password | 32 }}"
  DB_NAME: "{{ generate_slug }}"
  DB_HOST: "{{ network_alias | 'postgres' }}"

  # Connection string
  DATABASE_URL: "postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:5432/${DB_NAME}"

  # API configuration
  API_SECRET: "{{ generate_password | 64 }}"
  API_DOMAIN: "{{ generate_domain }}"

services:
  frontend:
    image: myapp/frontend:latest
    environment:
      API_URL: "https://${API_DOMAIN}"
    deploy:
      replicas: 2
      labels:
        zane.http.routes.0.domain: "myapp.com"
        zane.http.routes.0.port: "3000"
        zane.http.routes.0.base_path: "/"
        zane.http.routes.0.strip_prefix: "false"

  backend:
    image: myapp/backend:latest
    environment:
      DATABASE_URL: ${DATABASE_URL}
      SECRET_KEY: ${API_SECRET}
      PORT: "8080"
    depends_on:
      - postgres
    deploy:
      replicas: 3
      labels:
        zane.http.routes.0.domain: "${API_DOMAIN}"
        zane.http.routes.0.port: "8080"
        zane.http.routes.0.base_path: "/"
        zane.http.routes.0.strip_prefix: "false"

  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: ${DB_NAME}
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

---

### Example 3: App with Config Files

```yaml
x-zane-env:
  APP_NAME: "{{ generate_slug }}"
  DB_HOST: "{{ network_alias | 'postgres' }}"

services:
  web:
    image: nginx:alpine
    configs:
      - source: nginx_config
        target: /etc/nginx/nginx.conf
      - source: app_config
        target: /etc/app/config.json
    deploy:
      labels:
        zane.http.routes.0.domain: "example.com"
        zane.http.routes.0.port: "80"

configs:
  nginx_config:
    content: |
      user nginx;
      worker_processes auto;

      events {
        worker_connections 1024;
      }

      http {
        server {
          listen 80;
          server_name example.com;

          location / {
            root /usr/share/nginx/html;
            index index.html;
          }
        }
      }

  app_config:
    content: |
      {
        "app_name": "${APP_NAME}",
        "database": {
          "host": "${DB_HOST}",
          "port": 5432
        }
      }
```

---

### Example 4: Multi-Service with Multiple Domains

```yaml
x-zane-env:
  REDIS_HOST: "{{ network_alias | 'redis' }}"
  DB_HOST: "{{ network_alias | 'postgres' }}"
  DB_PASSWORD: "{{ generate_password | 32 }}"

services:
  web:
    image: myapp/web:latest
    environment:
      REDIS_URL: "redis://${REDIS_HOST}:6379"
    deploy:
      replicas: 2
      labels:
        # Main site
        zane.http.routes.0.domain: "example.com"
        zane.http.routes.0.port: "3000"
        zane.http.routes.0.base_path: "/"

        # www subdomain
        zane.http.routes.1.domain: "www.example.com"
        zane.http.routes.1.port: "3000"
        zane.http.routes.1.base_path: "/"
    depends_on:
      - redis

  api:
    image: myapp/api:latest
    environment:
      DATABASE_HOST: ${DB_HOST}
      DATABASE_PASSWORD: ${DB_PASSWORD}
    deploy:
      replicas: 3
      labels:
        # API subdomain
        zane.http.routes.0.domain: "api.example.com"
        zane.http.routes.0.port: "8080"
        zane.http.routes.0.base_path: "/"
    depends_on:
      - postgres

  postgres:
    image: postgres:16
    environment:
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:alpine
    volumes:
      - redis_data:/data

volumes:
  pgdata:
  redis_data:
```

---

### Example 5: WordPress with MySQL

```yaml
x-zane-env:
  MYSQL_ROOT_PASSWORD: "{{ generate_password | 32 }}"
  MYSQL_USER: "{{ generate_username }}"
  MYSQL_PASSWORD: "{{ generate_password | 32 }}"
  MYSQL_DATABASE: "{{ generate_slug }}"
  MYSQL_HOST: "{{ network_alias | 'mysql' }}"

  WP_DOMAIN: "{{ generate_domain }}"

services:
  wordpress:
    image: wordpress:6-apache
    environment:
      WORDPRESS_DB_HOST: ${MYSQL_HOST}
      WORDPRESS_DB_USER: ${MYSQL_USER}
      WORDPRESS_DB_PASSWORD: ${MYSQL_PASSWORD}
      WORDPRESS_DB_NAME: ${MYSQL_DATABASE}
    volumes:
      - wp_content:/var/www/html/wp-content
    depends_on:
      - mysql
    deploy:
      labels:
        zane.http.routes.0.domain: "${WP_DOMAIN}"
        zane.http.routes.0.port: "80"
        zane.http.routes.0.base_path: "/"
        zane.http.routes.0.strip_prefix: "false"

  mysql:
    image: mysql:8
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
      MYSQL_USER: ${MYSQL_USER}
      MYSQL_PASSWORD: ${MYSQL_PASSWORD}
      MYSQL_DATABASE: ${MYSQL_DATABASE}
    volumes:
      - mysql_data:/var/lib/mysql

volumes:
  wp_content:
  mysql_data:
```

---

## Dokploy Template Migration

ZaneOps includes an adapter to import templates from Dokploy. If you have existing Dokploy templates, here's how to migrate them.

### Dokploy Template Format

Dokploy templates are base64-encoded JSON containing:
- **compose**: Docker Compose YAML with placeholders
- **config**: TOML with variables, domains, env, and file mounts

Example Dokploy template structure (decoded):
```json
{
  "compose": "services:\n  web:\n    image: nginx\n    environment:\n      PASSWORD: ${password}\n",
  "config": "[variables]\npassword = \"${password:32}\"\n\n[[config.domains]]\nserviceName = \"web\"\nhost = \"example.com\"\nport = 80\n"
}
```

---

### Placeholder Mapping

Dokploy placeholders are automatically converted to ZaneOps template expressions:

| Dokploy Placeholder | ZaneOps Expression              |
| ------------------- | ------------------------------- |
| `${domain}`         | `{{ generate_domain }}`         |
| `${email}`          | `{{ generate_email }}`          |
| `${username}`       | `{{ generate_username }}`       |
| `${uuid}`           | `{{ generate_uuid }}`           |
| `${password}`       | `{{ generate_password \| 32 }}` |
| `${password:16}`    | `{{ generate_password \| 16 }}` |
| `${base64}`         | `{{ generate_password \| 32 }}` |
| `${base64:64}`      | `{{ generate_password \| 64 }}` |
| `${hash}`           | `{{ generate_password \| 32 }}` |
| `${hash:16}`        | `{{ generate_password \| 16 }}` |
| `${jwt}`            | `{{ generate_password \| 32 }}` |
| `${jwt:64}`         | `{{ generate_password \| 64 }}` |

---

### Conversion Process

The `DokployComposeAdapter.to_zaneops(base64_template)` method:

1. **Decode and parse**: Base64 → JSON → {compose, config}
2. **Convert placeholders**: Replace Dokploy placeholders with ZaneOps template expressions
3. **Process variables**: Extract `[variables]` section → `x-zane-env`
4. **Process domains**: Extract `[[config.domains]]` → `deploy.labels`
5. **Process mounts**: Convert `[[config.mounts]]` → inline configs
6. **Clean up**: Remove `ports`, `expose`, `restart`
7. **Output**: ZaneOps-compatible compose YAML

---

### Example Migration

**Dokploy compose.yaml**:
```yaml
services:
  web:
    image: nginx:alpine
    ports:
      - "8080:80"
    environment:
      DB_PASSWORD: ${DB_PASSWORD}
      ADMIN_EMAIL: ${ADMIN_EMAIL}
    volumes:
      - ../files/nginx.conf:/etc/nginx/nginx.conf
```

**Dokploy config.toml**:
```toml
[variables]
main_domain = "${domain}"
db_password = "${password:32}"
admin_email = "${email}"

[[config.domains]]
serviceName = "web"
host = "${main_domain}"
port = 8080

[[config.env]]
DB_PASSWORD = "${db_password}"
ADMIN_EMAIL = "${admin_email}"

[[config.mounts]]
filePath = "nginx.conf"
content = """
server {
  listen 80;
}
"""
```

**Resulting ZaneOps compose.yaml**:
```yaml
x-zane-env:
  main_domain: "{{ generate_domain }}"
  db_password: "{{ generate_password | 32 }}"
  admin_email: "{{ generate_email }}"
  DB_PASSWORD: ${db_password}
  ADMIN_EMAIL: ${admin_email}

services:
  web:
    image: nginx:alpine
    environment:
      DB_PASSWORD: ${DB_PASSWORD}
      ADMIN_EMAIL: ${ADMIN_EMAIL}
    configs:
      - source: nginx.conf
        target: /etc/nginx/nginx.conf
    deploy:
      labels:
        zane.http.routes.0.domain: "${main_domain}"
        zane.http.routes.0.port: "8080"
        zane.http.routes.0.base_path: "/"
        zane.http.routes.0.strip_prefix: "false"

configs:
  nginx.conf:
    content: |
      server {
        listen 80;
      }
```

---

### Mount Processing

Dokploy uses `../files/` prefix for file mounts. The adapter converts these to Docker configs.

**Case 1: Directory mount**

Dokploy:
```yaml
volumes:
  - ../files/clickhouse_config:/etc/clickhouse-server/config.d

[[config.mounts]]
filePath = "clickhouse_config/logging_rules.xml"
content = "..."

[[config.mounts]]
filePath = "clickhouse_config/network.xml"
content = "..."
```

ZaneOps result:
```yaml
configs:
  - source: logging_rules.xml
    target: /etc/clickhouse-server/config.d/logging_rules.xml
  - source: network.xml
    target: /etc/clickhouse-server/config.d/network.xml

configs:
  logging_rules.xml:
    content: "..."
  network.xml:
    content: "..."
```

---

**Case 2: File mount**

Dokploy:
```yaml
volumes:
  - ../files/nginx.conf:/etc/nginx/nginx.conf:ro

[[config.mounts]]
filePath = "nginx.conf"
content = "..."
```

ZaneOps result:
```yaml
configs:
  - source: nginx.conf
    target: /etc/nginx/nginx.conf

configs:
  nginx.conf:
    content: "..."
```

---

**Case 3: Non-existent path (becomes volume)**

Dokploy:
```yaml
volumes:
  - ../files/data:/app/data
```

If no matching mount exists → converted to named volume:
```yaml
volumes:
  - data:/app/data

volumes:
  data:
```

---

## Advanced Patterns

### Pattern 1: Shared Configuration Across Services

```yaml
x-zane-env:
  REDIS_HOST: "{{ network_alias | 'redis' }}"
  REDIS_PORT: "6379"
  REDIS_URL: "redis://${REDIS_HOST}:${REDIS_PORT}"

  DB_HOST: "{{ network_alias | 'postgres' }}"
  DB_USER: "{{ generate_username }}"
  DB_PASSWORD: "{{ generate_password | 32 }}"
  DB_NAME: "{{ generate_slug }}"
  DB_URL: "postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:5432/${DB_NAME}"

services:
  web:
    image: myapp/web:latest
    environment:
      REDIS_URL: ${REDIS_URL}
      DATABASE_URL: ${DB_URL}

  worker:
    image: myapp/worker:latest
    environment:
      REDIS_URL: ${REDIS_URL}
      DATABASE_URL: ${DB_URL}

  scheduler:
    image: myapp/scheduler:latest
    environment:
      REDIS_URL: ${REDIS_URL}
      DATABASE_URL: ${DB_URL}

  redis:
    image: redis:alpine

  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: ${DB_NAME}
```

**Benefit**: Single source of truth for connection strings.

---

### Pattern 2: Feature Flags via Environment

```yaml
x-zane-env:
  FEATURE_NEW_UI: "true"
  FEATURE_BETA_API: "false"
  FEATURE_ANALYTICS: "true"

services:
  app:
    image: myapp:latest
    environment:
      FEATURE_NEW_UI: ${FEATURE_NEW_UI}
      FEATURE_BETA_API: ${FEATURE_BETA_API}
      FEATURE_ANALYTICS: ${FEATURE_ANALYTICS}
```

**Benefit**: Toggle features by updating env overrides via API (no redeployment needed if app hot-reloads).

---

### Pattern 3: Zero-Downtime Service Pause

```yaml
services:
  worker:
    image: myapp/worker:latest
    deploy:
      replicas: 0  # Set to 0 to pause, > 0 to resume
```

**Benefit**: Pause services (e.g., background workers) without deleting the stack. Service status becomes `SLEEPING`.

---

### Pattern 4: Multi-Environment Configs

Use different configs per environment:

```yaml
x-zane-env:
  ENV_NAME: "production"  # Override via API for staging/dev
  LOG_LEVEL: "info"       # Override to "debug" for dev

services:
  app:
    image: myapp:latest
    environment:
      ENVIRONMENT: ${ENV_NAME}
      LOG_LEVEL: ${LOG_LEVEL}
```

**Benefit**: Same template, different behavior per environment via overrides.

---

### Pattern 5: Database Initialization Scripts

```yaml
services:
  postgres:
    image: postgres:16
    configs:
      - source: init_sql
        target: /docker-entrypoint-initdb.d/init.sql

configs:
  init_sql:
    content: |
      CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
      CREATE TABLE users (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        email TEXT UNIQUE NOT NULL
      );
```

**Benefit**: Initialize database schema on first startup.

---

## Troubleshooting

### Issue: Template Expression Not Evaluated

**Symptom**: Variable shows `{{ generate_password | 32 }}` literally instead of generated value.

**Cause**: Variable not defined in `x-zane-env`, or wrong syntax.

**Solution**:
```yaml
# ❌ Wrong - not in x-zane-env
services:
  app:
    environment:
      PASSWORD: "{{ generate_password | 32 }}"

# ✅ Correct
x-zane-env:
  PASSWORD: "{{ generate_password | 32 }}"

services:
  app:
    environment:
      PASSWORD: ${PASSWORD}
```

---

### Issue: Service Can't Connect to Another Service

**Symptom**: Connection refused or DNS resolution failure.

**Possible causes**:
1. **Wrong hostname**: Using hashed name instead of alias
2. **Service not started**: `depends_on` doesn't wait for readiness
3. **Network isolation**: Custom network without `zane` network

**Solution 1**: Use `network_alias` template function
```yaml
x-zane-env:
  DB_HOST: "{{ network_alias | 'postgres' }}"

services:
  app:
    environment:
      DATABASE_HOST: ${DB_HOST}
```

**Solution 2**: Use original service name (works in stack default network)
```yaml
services:
  app:
    environment:
      DATABASE_HOST: postgres  # Resolves to hashed name automatically
```

**Solution 3**: Add health check and retry logic in app
```javascript
// App code
async function connectWithRetry() {
  const maxRetries = 10;
  for (let i = 0; i < maxRetries; i++) {
    try {
      await db.connect();
      return;
    } catch (err) {
      await sleep(5000);
    }
  }
  throw new Error('Failed to connect');
}
```

---

### Issue: Invalid Route Configuration

**Symptom**: Deployment fails with route validation error.

**Common mistakes**:
```yaml
# ❌ Missing port
deploy:
  labels:
    zane.http.routes.0.domain: "example.com"

# ❌ Missing domain
deploy:
  labels:
    zane.http.routes.0.port: "80"

# ❌ Invalid port
deploy:
  labels:
    zane.http.routes.0.domain: "example.com"
    zane.http.routes.0.port: "not-a-number"

# ❌ Invalid strip_prefix
deploy:
  labels:
    zane.http.routes.0.domain: "example.com"
    zane.http.routes.0.port: "80"
    zane.http.routes.0.strip_prefix: "yes"  # Must be "true" or "false"
```

**Solution**: Ensure both domain and port are present and valid
```yaml
# ✅ Correct
deploy:
  labels:
    zane.http.routes.0.domain: "example.com"
    zane.http.routes.0.port: "80"
    zane.http.routes.0.base_path: "/"
    zane.http.routes.0.strip_prefix: "false"
```

---

### Issue: Config File Not Updated

**Symptom**: Changes to inline config `content` not reflected in container.

**Cause**: Config versioning - old config still referenced.

**Solution**:
1. Check deployed config version:
   ```bash
   docker config ls | grep nginx_config
   ```
2. Verify content changed (triggers version increment)
3. Redeploy stack (new version created automatically)

**Note**: If content is identical, version won't increment (working as intended).

---

### Issue: Volume Data Lost After Deployment

**Symptom**: Data in volume disappears after redeployment.

**Cause**: Volume not properly defined in the `volumes` section.

**Solution**: Always define named volumes in the top-level `volumes` section
```yaml
# ❌ Wrong - volume not defined
services:
  db:
    volumes:
      - pgdata:/var/lib/postgresql/data

# ✅ Correct - named volume properly defined
services:
  db:
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

---

### Issue: `generate_password` Invalid Length

**Symptom**: Deployment fails with "Password length must be even and >= 8".

**Cause**: Invalid length parameter.

**Solution**:
```yaml
# ❌ Wrong - odd length
x-zane-env:
  PASSWORD: "{{ generate_password | 31 }}"

# ❌ Wrong - too short
x-zane-env:
  PASSWORD: "{{ generate_password | 4 }}"

# ✅ Correct
x-zane-env:
  PASSWORD: "{{ generate_password | 32 }}"
```

**Valid lengths**: 8, 10, 12, 14, 16, 18, 20, ... (any even number 8 or greater)

---

### Issue: Environment Variable Not Expanded

**Symptom**: Variable shows `${VAR}` literally instead of expanded value.

**Cause**: Variable not defined in `x-zane-env`, or wrong syntax.

**Solution**:
```yaml
# ❌ Wrong - VAR not defined
services:
  app:
    environment:
      DATABASE_URL: "postgresql://user:pass@${DB_HOST}:5432/db"

# ✅ Correct - define in x-zane-env first
x-zane-env:
  DB_HOST: "{{ network_alias | 'postgres' }}"

services:
  app:
    environment:
      DATABASE_URL: "postgresql://user:pass@${DB_HOST}:5432/db"
```

---

### Issue: Service Won't Start (Deploy Fails)

**Symptom**: Deployment status shows `FAILED`.

**Common causes**:
1. **Invalid image**: Image doesn't exist or wrong tag
2. **Resource limits**: Not enough CPU/memory
3. **Invalid config**: Syntax error in inline config
4. **Port conflict**: Multiple routes to same port with conflicting paths

**Debug steps**:
1. Check deployment logs in ZaneOps UI
2. Check Docker service logs:
   ```bash
   docker service ps <service_id> --no-trunc
   docker service logs <service_id>
   ```
3. Verify image exists:
   ```bash
   docker pull <image>:<tag>
   ```
4. Check resource availability:
   ```bash
   docker node ls
   docker node inspect <node_id>
   ```

---

### Issue: Route Not Working (404)

**Symptom**: Domain resolves but returns 404.

**Possible causes**:
1. **Service not healthy**: Container running but app not listening
2. **Wrong port**: Route port doesn't match app listen port
3. **Base path mismatch**: App expects path prefix but strip_prefix=true

**Debug steps**:
1. Check service status in ZaneOps UI
2. Test service directly (bypass proxy):
   ```bash
   docker exec -it <container_id> curl localhost:<port>
   ```
3. Verify app is listening:
   ```bash
   docker exec -it <container_id> netstat -tlnp
   ```
4. Check Caddy config:
   ```bash
   docker exec -it <caddy_container> cat /etc/caddy/Caddyfile
   ```

---

## Best Practices

### 1. Use the Right Hostname for Service Communication

**Within the same stack**: Use the service name directly (simpler and works via the stack's default network).

```yaml
# ✅ Recommended for same-stack communication
services:
  app:
    environment:
      DB_HOST: postgres
      REDIS_HOST: redis
```

**Across different stacks in the same environment**: Use `network_alias` for stable, environment-scoped DNS.

```yaml
# ✅ Recommended for cross-stack communication (same environment)
x-zane-env:
  DB_HOST: "{{ network_alias | 'postgres' }}"
  REDIS_HOST: "{{ network_alias | 'redis' }}"
```

**Across different environments or globally in ZaneOps**: Use `global_alias` for globally unique DNS.

```yaml
# ✅ Recommended for cross-environment communication
x-zane-env:
  SHARED_DB: "{{ global_alias | 'postgres' }}"
```

**Why**: Service names are simplest for intra-stack communication. `network_alias` provides stable DNS for cross-stack scenarios within the same environment. `global_alias` is needed when communicating across environments or projects.

---

### 2. Use Named Volumes for Persistent Data

```yaml
# ✅ Recommended
volumes:
  pgdata:
  redis_data:
```

**Why**: Survives deployments and container recreation.

---

### 3. Version Control Your Compose Files

- Commit compose files to git
- Use branches for different environments
- Tag deployments in git

---

### 4. Use Inline Configs for Small Files

```yaml
# ✅ Good for configs < 100 lines
configs:
  nginx_config:
    content: |
      ...
```

**Why**: Easier to manage, version controlled, automatic versioning.

---

### 5. Set Resource Limits

```yaml
services:
  app:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 256M
```

**Why**: Prevents one service from consuming all resources.

---

### 6. Use Descriptive Variable Names

```yaml
# ❌ Unclear
x-zane-env:
  P1: "{{ generate_password | 32 }}"
  P2: "{{ generate_password | 32 }}"

# ✅ Clear
x-zane-env:
  DB_PASSWORD: "{{ generate_password | 32 }}"
  API_SECRET: "{{ generate_password | 64 }}"
```

---

### 7. Document Complex Templates

```yaml
# Database configuration
# Uses environment-scoped alias for stable DNS across PR previews
x-zane-env:
  DB_HOST: "{{ network_alias | 'postgres' }}"
  DB_USER: "{{ generate_username }}"
  DB_PASSWORD: "{{ generate_password | 32 }}"
```

---

### 8. Test Templates Locally First

Before deploying to ZaneOps:
1. Validate syntax with `docker compose config`
2. Test locally with `docker compose up`
3. Verify service communication
4. Check resource usage

---

## Summary

ZaneOps extends Docker Compose with powerful template expressions and automatic orchestration. Key takeaways:

1. **Use `x-zane-env`** for stack-wide variables with template expressions
2. **Template functions** generate secrets, domains, and service aliases
3. **Label-based routing** replaces port mappings
4. **Service name hashing** prevents DNS collisions
5. **Inline configs** with automatic versioning
6. **Named volumes** for persistent data
7. **`network_alias`** for stable inter-service communication
8. **Lazy computation** - templates processed on deployment only
9. **Value persistence** - generated secrets reused across deployments
10. **Dokploy compatibility** - easy migration from existing templates

