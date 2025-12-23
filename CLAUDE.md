# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## About ZaneOps

ZaneOps is a self-hosted, open-source PaaS (Platform as a Service) for deploying web apps, static sites, databases, and services. It's an alternative to Heroku, Railway, and Render, built with Docker Swarm for scalability and Caddy for HTTP routing.

## Tech Stack

- **Backend**: Django 5.2, Django REST Framework, Python 3.12+
- **Frontend**: React 19, React Router 7, Vite, TypeScript, TailwindCSS 4
- **Infrastructure**: Docker Swarm, Caddy (reverse proxy)
- **Async Processing**: Temporal.io for workflows and long-running tasks
- **Database**: PostgreSQL 16
- **Cache**: Redis (Valkey 7.2.5)
- **Logging**: Fluentd, Loki, Grafana
- **Package Managers**: pnpm (frontend/workspace), uv (Python backend)

## Development Setup

### Initial Setup

```bash
# Clone and setup the project
make setup
```

This will:
- Initialize Docker Swarm if not already initialized
- Create the `zane` overlay network for Docker Swarm
- Install Python dependencies via uv in backend/.venv
- Install Node.js dependencies via pnpm

### Environment Configuration

1. Copy `.env.example` to `.env` (root)
2. Copy `frontend/.env.example` to `frontend/.env`
3. Obtain a webhook.site token from https://webhook.site for webhooks and configure:
   - `VITE_WEBHOOK_SITE_TOKEN` in `frontend/.env`
   - `WH_TOKEN` in `.env`

### Running the Development Server

```bash
# Start all services (frontend + backend + dependencies)
make dev

# Start only backend services (excluding frontend)
make dev-api

# After starting, run migrations
make migrate
```

The app will be available at http://localhost:5173

### Database Management

```bash
# Run migrations
make migrate

# Create new migrations
cd backend && . .venv/bin/activate && python manage.py makemigrations

# Reset database (WARNING: destroys all data)
make reset-db
```

## Common Development Commands

### Backend (Django)

All backend commands should be run with the virtual environment activated from the `backend/` directory:

```bash
cd backend
. .venv/bin/activate

# Run Django development server
python manage.py runserver 0.0.0.0:8000

# Run tests (all)
python manage.py test --settings=backend.settings_test --parallel

# Run specific tests (filter by pattern)
python manage.py test --settings=backend.settings_test --parallel -k <pattern>

# Django shell with IPython
python manage.py shell -i ipython

# Generate OpenAPI schema
python manage.py spectacular --color --file ../openapi/schema.yml

# Lock dependencies
uv lock
```

### Frontend (React + Vite)

```bash
cd frontend

# Generate API client from OpenAPI schema
pnpm generate:api

# Run dev server
pnpm dev

# Build for production
pnpm build

# Type checking
pnpm typecheck
```

### Workspace Root

```bash
# Format code with Biome (frontend + docker)
pnpm format

# Run all tests
pnpm test

# Generate API schema and client
pnpm gen:api
```

## Architecture Overview

### Backend Architecture

The Django backend is organized into several key apps:

1. **`backend/zane_api/`** - Main API application
   - `models/` - Django models split by concern:
     - `main.py` - Core models (Project, Service, Deployment, Environment, etc.)
     - `base.py` - Base/abstract models
     - `archived.py` - Archived/soft-deleted entities
   - `views/` - API endpoints organized by resource (projects, services, deployments, etc.)
   - `serializers.py` - DRF serializers for API responses
   - `tests/` - Unit and integration tests

2. **`backend/temporal/`** - Temporal.io workflow orchestration
   - `workflows/` - Long-running workflows (deploy services, manage environments, etc.)
   - `activities/` - Atomic units of work called by workflows
   - `schedules/` - Scheduled tasks (cleanup, monitoring)
   - `worker.py` - Temporal worker process

3. **`backend/git_connectors/`** - GitHub/GitLab integration
4. **`backend/container_registry/`** - Docker registry integration
5. **`backend/s3_targets/`** - S3 storage integration
6. **`backend/webshell/`** - Web-based shell access
7. **`backend/search/`** - Search functionality

### Frontend Architecture

React Router 7 application with file-based routing:

- **`frontend/app/routes/`** - Route definitions
  - `projects/` - Project management views
  - `services/` - Service configuration and deployment
  - `deployments/` - Deployment history and status
  - `environments/` - Environment management
  - `settings/` - User/project settings
- **`frontend/app/api/`** - Auto-generated API client from OpenAPI schema
- Uses TanStack Query for data fetching and caching
- Radix UI for accessible component primitives
- Monaco Editor for code editing
- XTerm for terminal emulation

### Temporal Workflows

Temporal.io handles all asynchronous, long-running operations:

- **Service deployments** - Build images, manage containers, update proxy config
- **Environment management** - Create, clone, destroy environments
- **Scheduled tasks** - Metrics cleanup, health checks, auto-updates
- **Git operations** - Clone repos, checkout branches, track commits

Two worker processes run different task queues:
- `temporal-main-worker` - General workflows (default queue)
- `temporal-schedule-worker` - Scheduled/recurring tasks (`schedule-task-queue`)

### Docker Swarm Integration

- **Overlay network**: All services communicate via the `zane` overlay network
- **Service naming**: Services use DNS aliases (e.g., `zane.db`, `zane.api`, `zane.temporal`)
- **Caddy proxy**: Routes HTTP traffic to deployed services, manages SSL/TLS
- User deployments run as Docker Swarm services with labels for identification

### Data Flow

1. User creates/deploys a service via frontend
2. API creates database records and starts Temporal workflow
3. Temporal workflow:
   - Clones git repository (if needed)
   - Builds Docker image
   - Creates/updates Docker Swarm service
   - Configures Caddy proxy routes
4. Deployment status streamed via WebSockets (Django Channels)
5. Runtime logs collected via Fluentd → Loki → API

## Testing

### Backend Tests

- Located in `backend/zane_api/tests/`
- Use Django's test framework with custom `RedGreenUnittest` runner
- Tests use `settings_test.py` configuration
- Run with `--parallel` for speed

### Frontend

- No test suite currently configured

## Code Style

### Backend (Python)

- Use `black` for formatting (configured in pyproject.toml)
- Use `isort` for import sorting
- Follow Django conventions
- Type hints encouraged but not strictly enforced

### Frontend (TypeScript/JavaScript)

- Use Biome for formatting (configured in biome.json)
- 2-space indentation
- 80 character line width
- Format before committing: `pnpm format`

## Important Patterns

### Service Models

The `Service` model in `backend/zane_api/models/main.py` is the core entity representing deployable services. Key concepts:

- **Service types**: Docker (pre-built image) vs Git (build from source)
- **Deployments**: Each service has multiple deployment records tracking changes
- **Environments**: Services exist within environments (production, preview, custom)
- **URL configuration**: Services have domains, custom domains, and path routing

### Temporal Activities

Activities in `backend/temporal/activities/` are decorated with `@activity.defn` and:
- Should be idempotent when possible
- Use heartbeats for long-running operations
- Raise `ApplicationError` for business logic failures
- Return serializable data structures

### API Schema Generation

The OpenAPI schema is auto-generated from Django REST Framework views:

1. Backend generates schema: `python manage.py spectacular`
2. Frontend generates TypeScript client: `pnpm generate:api`
3. Client available at `frontend/app/api/v1.ts`

Do not manually edit the generated API client.

## Docker Services

Development uses both Docker Compose and Docker Stack:

- **docker-compose.yaml** - Local development services (DB, Redis, Temporal, etc.)
- **docker-stack.yaml** - Swarm services (Caddy proxy)

Start/stop stack services:
```bash
cd docker
./start-docker-stack.sh
./stop-docker-stack.sh
```

## Debugging

### Common Issues

1. **Services not reachable**: Check all Docker containers are running (especially Caddy proxy)
2. **API errors**: Check `make dev` logs for Django errors
3. **Database issues**: Try `make reset-db` (destroys all data)
4. **Temporal workflow failures**: Check Temporal UI at http://localhost:8082

### Useful Debug Commands

```bash
# View Docker Swarm services
docker service ls

# View service logs
docker service logs <service-name>

# Access Django shell
cd backend && . .venv/bin/activate && python manage.py shell -i ipython

# View Temporal workflows
# Navigate to http://localhost:8082
```

## Dependencies

### Backend

Managed by `uv` with `pyproject.toml` and `uv.lock`:
- Django and DRF for API
- Temporal SDK for workflows
- Docker SDK for container management
- Channels for WebSockets
- GitPython for Git operations
- boto3 for S3 integration

### Frontend

Managed by `pnpm` with workspace support:
- React 19 with React Router 7
- TanStack Query for data fetching
- Radix UI for components
- Monaco Editor for code editing
- OpenAPI TypeScript for API client generation

## Project Constraints

- **Python version**: Requires Python 3.12+
- **Node version**: Requires Node.js 20 (specified in package.json engines)
- **Docker Swarm**: Required for deployment features (auto-initialized by `make setup`)
- **PostgreSQL**: Required for persistence
- **Redis**: Required for caching and Channels
