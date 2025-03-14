.DEFAULT_GOAL := help

help:  ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

setup: ## Initial setup of the project including swarm, network, virtualenv, and dependencies
	@echo "Creating a virtual env..."
	@echo "Initializing docker swarm (if not already active)..."
	@if docker info --format '{{.Swarm.LocalNodeState}}' | grep -qw "active"; then \
		if docker info --format '{{.Swarm.ControlAvailable}}' | grep -qw "true"; then \
			echo "Swarm is enabled and this node is a manager, skipping swarm initialization 👍"; \
		else \
			echo "❌ ERROR: Swarm is enabled, but this node is not a manager. ZaneOps needs be installed on a docker swarm manager. ❌" >&2; \
			echo "To promote this node to a manager, run: docker node promote <node_name>" >&2; \
			echo "You can check the node name by running: docker node ls" >&2; \
			exit 1; \
		fi \
	else \
		docker swarm init; \
	fi
	@echo "Creating zane network (if not already present)..."
	@if docker network ls | grep -qw "zane"; then \
    	echo "Zane network already exists, skipping"; \
	else \
    	docker network create --attachable --driver overlay --label zane.stack=true zane; \
	fi
	@echo "Creating backend virtual environment..."
	@python3 -m venv ./backend/venv
	@echo "Activating the virtualenv..."
	@chmod a+x ./backend/venv/bin/activate
	@./backend/venv/bin/activate; \
	@echo "Installing backend dependencies using uv..."
	@./backend/venv/bin/pip install --upgrade pip
	@./backend/venv/bin/uv pip install -r ./backend/requirements.txt
	@echo "Installing frontend dependencies using pnpm..."
	@pnpm install --frozen-lockfile
	@echo "Setting execution permissions for scripts..."
	@chmod -R a+rx ./docker/temporalio/*.sh
	@echo "Setup complete! ✅"

deploy-temporal-ui: ## Deploy Temporal UI using Docker stack
	@echo "Deploying Temporal UI..."
	@docker stack deploy --with-registry-auth --detach=false --compose-file docker-stack.prod-temporal-ui.yaml zane-temporal-ui

stop-temporal-ui: ## Stop Temporal UI Docker stack
	@echo "Stopping Temporal UI..."
	@docker stack rm zane-temporal-ui

migrate: ## Run database migrations
	@echo "Running database migrations..."
	@./backend/venv/bin/activate && python ./backend/manage.py migrate

dev: ## Start the development server in parallel
	@echo "Starting development servers..."
	@pnpm run --recursive --parallel dev

reset-db: ## Wipe out the database and reset the application to its initial state
	@echo "Resetting the database..."
	@chmod a+x reset-db.sh
	@./reset-db.sh
