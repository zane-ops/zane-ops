.PHONY: all clean test setup help stop deploy create-user delete-resources

SHELL := /bin/bash
current_dir = $(shell pwd)
db_password = "$(shell openssl rand -base64 32)"
django_secret = "$(shell openssl rand -base64 48 | tr -d '=+/ ' | cut -c1-64)"
db_username = "$(shell curl -s https://randomuser.me/api/ | jq -r '.results[0].login.username')"
ip_address="$(shell hostname -I | awk '{print $1}' | sed 's/\./-/g')"
.DEFAULT_GOAL := help

help: ### Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

setup: ### Launch initial setup before installing zaneops
	@echo "⚒️⚒️⚒️⚒️⚒️⚒️⚒️⚒️⚒️⚒️⚒️⚒️⚒️⚒️⚒️⚒️⚒️⚒️⚒️"
	@echo "    ⚒️  INITIAL SETUP OF ZANEOPS ⚒️"
	@echo "⚒️⚒️⚒️⚒️⚒️⚒️⚒️⚒️⚒️⚒️⚒️⚒️⚒️⚒️⚒️⚒️⚒️⚒️⚒️"
	@echo "Step 1️⃣ : initializing docker swarm..."
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
	@curl https://raw.githubusercontent.com/zane-ops/zane-ops/main/docker/attach-proxy-networks.sh > ./attach-proxy-networks.sh
	@curl https://raw.githubusercontent.com/zane-ops/zane-ops/main/docker/fluentd/fluent.conf > ./fluent.conf
	@curl https://raw.githubusercontent.com/zane-ops/zane-ops/main/docker/docker-stack.prod-temporal-ui.yaml > ./docker-stack.prod-temporal-ui.yaml
	@chmod a+x ./attach-proxy-networks.sh
	@chmod -R a+x ./temporalio/*.sh
	@echo "Step 3️⃣ Done ✅"
	@echo "Step 4️⃣: Downloading the env file template..."
	@if [ ! -f ".env" ]; then \
		curl https://raw.githubusercontent.com/zane-ops/zane-ops/main/.env.template > ./.env; \
		sed -i'.bak' "s#{{INSTALL_DIR}}#$(current_dir)#g" ./.env; \
		sed -i'.bak' "s#{{ZANE_DB_USER}}#\"$(db_username)\"#g" ./.env; \
		sed -i'.bak' "s#{{ZANE_DB_PASSWORD}}#\"$(db_password)\"#g" ./.env; \
		sed -i'.bak' "s#{{ZANE_DJANGO_SECRET_KEY}}#\"$(django_secret)\"#g" ./.env; \
		if [ $$(uname) = "Linux" ]; then \
			sed -i'.bak' "s#127-0-0-1#$(ip_address)#g" ./.env; \
		fi
		echo "Your .env file has been generated with: " \
		if [ $$(uname) = "Linux" ]; then \
			echo "ROOT_DOMAIN=\"\x1b[94m$(ip_address).sslip.io\x1b[0m\""; \
			echo "ZANE_APP_DOMAIN=\"\x1b[94m$(ip_address).sslip.io\x1b[0m\";  \
		else \
			echo "ROOT_DOMAIN=\"\x1b[94m127-0-0-1.sslip.io\x1b[0m\""; \
			echo "ZANE_APP_DOMAIN=\"\x1b[94m127-0-0-1.sslip.io\x1b[0m\";  \
		fi
		echo "__DANGEROUS_ALLOW_HTTP_SESSION=\"\x1b[94mtrue\x1b[0m\"";  \
		echo "⚠️ PLEASE DON'T FORGET TO CHANGE THESE ON PRODUCTION ⚠️"; \
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

deploy: ### Install and deploy zaneops
	@echo "🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀"
	@echo "    🚀   DEPLOYMENT OF ZANEOPS   🚀"
	@echo "🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀"
	@echo "Deploying zaneops...🔄"
	@set -a; . ./.env; set +a && docker stack deploy --with-registry-auth --compose-file docker-stack.prod.yaml --compose-file docker-stack.prod-http.yaml zane;
	@. ./attach-proxy-networks.sh
	@docker service ls --filter "label=zane-managed=true" --filter "label=status=active" -q | xargs -P 0 -I {} docker service scale --detach {}=1
	@echo "🏁 Deploy done, Please give this is a little minutes before accessing your website 🏁"
	@echo "You can monitor the services deployed by running \x1b[92mdocker service ls --filter label=\"zane.stack=true\"\x1b[0m"
	@echo "Wait for all services (except for \`zane_temporal-admin-tools\`) to show up as \x1b[92mreplicated   1/1\x1b[0m to attest that everything started succesfully"

create-user: ### Create the first user to login in into the dashboard
	@docker exec -it $$(docker ps -qf "name=zane_api") /bin/bash -c "source /venv/bin/activate && python manage.py createsuperuser"

stop: ### Take down zaneops and scale down all services created in zaneops
	@echo "Taking down zaneops..."
	docker stack rm zane
	@echo "Scaling down services created in zaneops..., use \`make deploy\` to restart them"
	@docker service ls --filter "label=zane-managed=true" -q | xargs -P 0 -I {} docker service scale --detach {}=0

delete-resources: ### Delete all resources created by zaneops
	@echo "Taking down zaneops..."
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
