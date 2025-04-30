.DEFAULT_GOAL := help
help: ### Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

setup: ### Initial setup of the project
	echo 'Creating a virtual env...'
	echo 'initializating docker swarm'
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
	@if docker network ls | grep -qw "zane"; then \
    	echo "Zane network already exists, skipping"; \
	else \
    	docker network create --attachable --driver overlay --label zane.stack=true zane; \
	fi
	python3 -m pip install uv
	cd backend/ && uv sync
	echo 'activating the virtualenv...'
	chmod a+x ./backend/.venv/bin/activate
	. ./backend/.venv/bin/activate
	pnpm install --frozen-lockfile
	chmod -R a+rx ./docker/temporalio/*.sh

deploy-temporal-ui:
	docker stack deploy --with-registry-auth --detach=false --compose-file docker-stack.prod-temporal-ui.yaml zane-temporal-ui

stop-temporal-ui:
	docker stack rm zane-temporal-ui

migrate: ### Run db migration
	. ./backend/.venv/bin/activate && python ./backend/manage.py migrate

dev: ### Start the DEV server
	pnpm run --recursive --parallel dev

reset-db: ### Wipe out the database and reset the application to its initial state
	chmod a+x reset-db.sh
	./reset-db.sh
