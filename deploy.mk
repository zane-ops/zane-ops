.PHONY: all clean test setup help stop deploy create-user delete-resources setup-v2

SHELL := /bin/bash
current_dir = $(shell pwd)
db_password = "$(shell openssl rand -base64 32)"
django_secret = "$(shell openssl rand -base64 48 | tr -d '=+/ ' | cut -c1-64)"
db_username = "$(shell curl -s https://randomuser.me/api/ | jq -r '.results[0].login.username')"
.DEFAULT_GOAL := help
help: ### Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

setup: ### Launch initial setup before installing zaneops
	@echo -e "====== \x1b[94m⚒️  INITIAL SETUP OF ZANEOPS ⚒️\x1b[0m ======"
	@echo "Step 1️⃣ : Verifying docker swarm status..."
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
		echo -e "❌ ERROR: Docker Swarm is disabled, please enable it with \x1b[96mdocker swarm init --advertise-addr <SERVER_IP>\x1b[0m. ZaneOps needs be installed on a docker swarm manager. ❌" >&2; \
		echo -e "\x1b[96mSERVER_IP\x1b[0m is the IP address of your server:"; \
		echo -e "> You can use your server's public IP."; \
		echo -e "> If you have private networking, use the private IP (e.g., \x1b[33m10.0.0.x\x1b[0m)."; \
		echo -e "> If you are installing locally, use \x1b[33m127.0.0.1\x1b[0m."; \
		echo "\nSee docs for more information : \x1b[96mhttps://zaneops.dev/installation/#process\x1b[0m"; \
		exit 1; \
	fi
	@echo "Step 1️⃣ Done ✅"
	@echo "Step 2️⃣: Preparing the current folder..."
	@mkdir -p .fluentd
	@chmod 777 .fluentd
	@echo "Step 2️⃣ Done ✅"
	@echo "Step 3️⃣: Downloading docker compose files for zaneops..."
	@mkdir -p $(current_dir)/temporalio/config/dynamicconfig
	@curl https://raw.githubusercontent.com/zane-ops/zane-ops/main/docker/temporalio/entrypoint.sh > ./temporalio/entrypoint.sh
	@curl https://raw.githubusercontent.com/zane-ops/zane-ops/main/docker/temporalio/admin-tools-entrypoint.sh > ./temporalio/admin-tools-entrypoint.sh
	@curl https://raw.githubusercontent.com/zane-ops/zane-ops/main/docker/temporalio/config/config_template.yaml > ./temporalio/config/config_template.yaml
	@curl https://raw.githubusercontent.com/zane-ops/zane-ops/main/docker/temporalio/config/dynamicconfig/production-sql.yaml > ./temporalio/config/dynamicconfig/production-sql.yaml
	@curl https://raw.githubusercontent.com/zane-ops/zane-ops/main/docker/docker-stack.prod.yaml > ./docker-stack.prod.yaml
	@curl https://raw.githubusercontent.com/zane-ops/zane-ops/main/docker/docker-stack.prod-http.yaml > ./docker-stack.prod-http.yaml
	@curl https://raw.githubusercontent.com/zane-ops/zane-ops/main/docker/fluentd/fluent.conf > ./fluent.conf
	@chmod -R a+x ./temporalio/*.sh
	@echo "Step 3️⃣ Done ✅"
	@echo "Step 4️⃣: Downloading the env file template..."
	@if [ ! -f ".env" ]; then \
		curl https://raw.githubusercontent.com/zane-ops/zane-ops/main/.env.template > ./.env; \
		sed -i'.bak' "s#{{INSTALL_DIR}}#$(current_dir)#g" ./.env; \
		sed -i'.bak' "s#{{ZANE_DB_USER}}#\"$(db_username)\"#g" ./.env; \
		sed -i'.bak' "s#{{ZANE_DB_PASSWORD}}#\"$(db_password)\"#g" ./.env; \
		sed -i'.bak' "s#{{ZANE_DJANGO_SECRET_KEY}}#\"$(django_secret)\"#g" ./.env; \
		if [ "$(shell uname)" = "Linux" ]; then \
			IP_ADDRESS=$(shell ip route show default | awk '/src/ {for (i=1; i<=NF; i++) if ($$i=="src") print $$(i+1)}' |  sed 's/\./-/g'); \
			sed -i "s/127-0-0-1/$$IP_ADDRESS/g" .env; \
			echo -e "default ZaneOps domain configured to \x1b[96m$$IP_ADDRESS.sslip.io\x1b[0m in the .env file ✅"; \
		fi; \
		rm .env.bak; \
  	fi
	@echo "Step 4️⃣ Done ✅"
	@echo "Step 5️⃣: Create docker network for zaneops..."
	@if docker network ls | grep -qw "zane"; then \
    	echo "Zane network already exists, skipping"; \
	else \
    	docker network create --attachable --driver overlay --label zane.stack=true zane; \
	fi
	@echo "Step 5️⃣ Done ✅"
	@echo "Setup finished 🏁"

deploy: ### Install and deploy zaneops based on MODE (https or http)
	@set -a; . ./.env; set +a; \
	if [ "$$MODE" = "https" ]; then \
		echo -e "====== \x1b[94mDeploying ZaneOps \x1b[92mwith HTTPS 🔒\x1b[0m ======"; \
		docker stack deploy --detach --with-registry-auth --compose-file docker-stack.prod.yaml zane; \
		ACCESS_URL="https://$$ZANE_APP_DOMAIN"; \
	elif [ "$$MODE" = "http" ]; then \
		echo -e "====== \x1b[94mDeploying ZaneOps\x1b[0m \x1b[38;5;208m⚠️  with HTTP enabled ⚠️\x1b[0m  ======"; \
		docker stack deploy --detach --with-registry-auth --compose-file docker-stack.prod.yaml --compose-file docker-stack.prod-http.yaml zane; \
		ACCESS_URL="http://$$ZANE_APP_DOMAIN"; \
	else \
		echo -e "\x1b[91mError: MODE must be either 'https' or 'http'\x1b[0m"; \
		exit 1; \
	fi; \
	docker service ls --filter "label=zane-managed=true" --filter "label=status=active" -q | xargs -P 0 -I {} docker service scale --detach {}=1; \
	echo -e "\n🏁 Deploy done, Please give this is a little minutes before accessing your website 🏁"; \
	echo -e "\n> You can monitor the services deployed by running \x1b[96mdocker service ls --filter label=\x1b[33m\"zane.stack=true\"\x1b[0m"; \
	echo -e "  And wait for all services (except for \x1b[90mzane_temporal-admin-tools\x1b[0m) to show up as \x1b[96mreplicated   1/1\x1b[0m to attest that everything started succesfully"; \
	echo -e "\n> You can also monitor the new versions of the services by running \x1b[96mdocker ps --filter label=\x1b[33m\"com.docker.stack.namespace=zane\"\x1b[0m"; \
	echo -e "  And wait for all services to show up as \x1b[96m(healthy)\x1b[0m to attest that everything started succesfully"; \
	echo -e "\nit can take up to 5 minutes to start on the first deploy. \x1b[96m$$ACCESS_URL\x1b[0m"; \
	echo -e "\nOnce everything is ok, zaneops will be accessible at \x1b[96m$$ACCESS_URL\x1b[0m"; \
	echo -e "====== \x1b[94mDONE Deploying ZaneOps ✅\x1b[0m ======"

create-user: ### Create the first user to login in into the dashboard
	@docker exec -it $$(docker ps -qf "name=zane_app") /bin/bash -c "source /venv/bin/activate && python manage.py createsuperuser"

reset-password: ### Reset user password
	@if [ -z "$(user)" ]; then echo -e "Error: \x1b[33m\$$user\x1b[0m variable is required. Usage: \x1b[96mmake reset-password user=username\x1b[0m"; exit 1; fi
	@docker exec -it $$(docker ps -qf "name=zane_app") /bin/bash -c "source /venv/bin/activate && python manage.py changepassword $(user)"

stop: ### Take down zaneops and scale down all services created in zaneops
	@echo -e "====== \x1b[94mTaking down zaneops...\x1b[0m ======"
	@docker stack rm zane
	@echo -e "Scaling down services created in zaneops..., use \x1b[96mmake deploy\x1b[0m to restart them"
	@docker service ls --filter "label=zane-managed=true" -q | xargs -P 0 -I {} docker service scale --detach {}=0
	@echo -e "====== \x1b[94mDONE ✅\x1b[0m ======"

delete-resources: ### Delete all resources created by zaneops
	@echo -e "====== \x1b[91mDELETING ZaneOps and all its created resources...\x1b[0m ======"
	docker stack rm zane
	@echo "Removing zane-ops volumes..."
	@echo "Waiting for all containers related to services to be removed..."
	@while [ -n "$$(docker ps -a | grep "zane_" | awk '{print $$1}')" ]; do \
		sleep 2; \
	done
	docker volume rm $$(docker volume ls --filter "label=zane.stack=true" -q)
	@echo "Removing all services created by zane-ops..."
	docker service rm $$(docker service ls --filter "label=zane-managed=true" -q) || true
	@echo "Waiting for all containers related to services to be removed..."
	@while [ -n "$$(docker ps -a | grep "srv-prj_" | awk '{print $$1}')" ]; do \
		sleep 2; \
	done
	@echo "Removing all networks created by zane-ops..."
	docker network rm $$(docker network ls --filter "label=zane-managed=true" -q) || true
	@echo "Removing all volumes created by zane-ops..."
	docker volume rm $$(docker volume ls --filter "label=zane-managed=true" -q) || true
	@echo "Removing zane-ops network..."
	docker network rm zane
	@echo "Cleaning up unused docker resources..."
	docker system prune -f --volumes
	@echo -e "====== \x1b[94mDONE deleting ZaneOps, it is safe to delete this folder ✅\x1b[0m ======"