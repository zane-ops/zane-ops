.DEFAULT_GOAL := help
help: ### Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

setup: ### Initial setup of the project
	echo 'Creating a virtual env...'
	docker network create --driver overlay zane || true
	python3 -m venv ./backend/venv
	echo 'activating the virtualenv...'
	chmod a+x ./backend/venv/bin/activate
	./backend/venv/bin/activate
	echo 'installing dependencies...'
	pip install uv
	uv pip install -r ./backend/requirements.txt
	pnpm install --frozen-lockfile
	echo 'initializating docker swarm'
	docker swarm init || true

migrate: ### Run db migration
	./backend/venv/bin/activate
	python ./backend/manage.py migrate

dev: ### Start the DEV server
	pnpm run  --filter='!backend' --recursive --parallel dev

dev-api: ### Start the API server
	pnpm run  --filter='backend' --recursive dev

reset-db: ### Wipe out the database and reset the application to its initial state
	chmod a+x reset-db.sh
	./reset-db.sh
