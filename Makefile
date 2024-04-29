.DEFAULT_GOAL := help
help: ### Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

setup: ### Initial setup of the project
	echo 'Creating a virtual env...'
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
	pnpm --recursive --parallel run dev
