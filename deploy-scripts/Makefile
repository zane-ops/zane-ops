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
	@mkdir -p $(current_dir)/pgbouncer
	@mkdir -p $(current_dir)/temporalio/config/dynamicconfig
	@curl https://raw.githubusercontent.com/zane-ops/zane-ops/main/docker/temporalio/entrypoint.sh > ./temporalio/entrypoint.sh
	@curl https://raw.githubusercontent.com/zane-ops/zane-ops/main/docker/temporalio/admin-tools-entrypoint.sh > ./temporalio/admin-tools-entrypoint.sh
	@curl https://raw.githubusercontent.com/zane-ops/zane-ops/main/docker/temporalio/config/config_template.yaml > ./temporalio/config/config_template.yaml
	@curl https://raw.githubusercontent.com/zane-ops/zane-ops/main/docker/temporalio/config/dynamicconfig/production-sql.yaml > ./temporalio/config/dynamicconfig/production-sql.yaml
	@curl https://raw.githubusercontent.com/zane-ops/zane-ops/main/docker/docker-stack.prod.yaml > ./docker-stack.prod.yaml
	@curl https://raw.githubusercontent.com/zane-ops/zane-ops/main/docker/docker-stack.prod-http.yaml > ./docker-stack.prod-http.yaml
	@curl https://raw.githubusercontent.com/zane-ops/zane-ops/main/docker/fluentd/fluent.conf > ./fluent.conf
	@curl https://raw.githubusercontent.com/zane-ops/zane-ops/main/docker/loki/config.yaml > ./loki-config.yaml
	@curl https://raw.githubusercontent.com/zane-ops/zane-ops/main/docker/docker-stack.prod-temporal-ui.yaml > ./docker-stack.prod-temporal-ui.yaml
	@curl https://raw.githubusercontent.com/zane-ops/zane-ops/main/docker/docker-stack.prod-otel.yaml > ./docker-stack.prod-otel.yaml
	@curl https://raw.githubusercontent.com/zane-ops/zane-ops/main/docker/tempo/config.yaml > ./tempo-config.yaml
	@curl https://raw.githubusercontent.com/zane-ops/zane-ops/main/docker/grafana/datasources/datasource.yaml > ./grafana-datasources.yaml
	@curl https://raw.githubusercontent.com/zane-ops/zane-ops/main/docker/pgbouncer/entrypoint.sh > ./pgbouncer/entrypoint.sh
	@chmod -R a+x ./temporalio/*.sh
	@chmod -R a+x ./pgbouncer/*.sh
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
		docker stack deploy --detach --with-registry-auth --prune --compose-file docker-stack.prod.yaml zane; \
		ACCESS_URL="https://$$ZANE_APP_DOMAIN"; \
	elif [ "$$MODE" = "http" ]; then \
		echo -e "====== \x1b[94mDeploying ZaneOps\x1b[0m \x1b[38;5;208m⚠️  with HTTP enabled ⚠️\x1b[0m  ======"; \
		docker stack deploy --detach --with-registry-auth --prune --compose-file docker-stack.prod.yaml --compose-file docker-stack.prod-http.yaml zane; \
		ACCESS_URL="http://$$ZANE_APP_DOMAIN"; \
	else \
		echo -e "\x1b[91mError: MODE must be either 'https' or 'http'\x1b[0m"; \
		exit 1; \
	fi; \
	docker service ls --filter "label=zane-managed=true" --filter "label=status=active" -q | xargs -P 0 -I {} docker service scale --detach {}=1; \
	echo -e "\n🏁 Deploy initiated"; \
	spinner=( '◐' '◓' '◑' '◒' ); i=0; \
	deploy_timeout=$${DEPLOY_TIMEOUT:-300}; started=$$SECONDS; timed_out=0; \
	while true; do \
		incomplete=0; \
		while IFS=";" read -r svc_name svc_replicas; do \
			if [[ "$$svc_name" == *"temporal-admin-tools" ]]; then \
				if [[ "$$svc_replicas" != "0/1 (1/1 completed)" ]]; then \
					incomplete=1; \
					break; \
				fi; \
			else \
				if [[ "$$svc_replicas" != "1/1" ]]; then \
					incomplete=1;\
					break; \
				fi; \
			fi; \
		done < <(docker service ls --filter "name=zane_" --format "{{.Name}};{{.Replicas}}"); \
		if [ $$incomplete -eq 0 ]; then break; fi; \
		if [ $$(( SECONDS - started )) -ge $$deploy_timeout ]; then timed_out=1; break; fi; \
		printf "\rWaiting for all services to reach desired state, this should take less than 5 minutes... \033[33m%s\033[0m " "$${spinner[$$((i % 4))]}"; \
		i=$$((i+1)); \
		sleep 0.1; \
	done; \
	if [ $$timed_out -eq 1 ]; then \
		printf "\rWaiting for all services to reach desired state... \033[33mgave up after %ss\033[0m ⏱                 \n" "$$deploy_timeout"; \
	else \
		printf "\rWaiting for all services to reach desired state... Done 💓                                 \n"; \
	fi; \
	stuck=$$(for svc in $$(docker service ls --filter "name=zane_" --format '{{.Name}}'); do \
		docker service ps "$$svc" --no-trunc --filter "desired-state=running" --format '{{.CurrentState}}' \
			| grep -q '^Pending' && echo "$$svc"; \
	done); \
	if [ -n "$$stuck" ]; then \
		echo -e "\n\x1b[38;5;208m⚠️  Warning: the rollout of these services is stuck in 'Pending':\x1b[0m"; \
		for svc in $$stuck; do \
			reason=$$(docker service ps "$$svc" --no-trunc --filter "desired-state=running" --format '{{.Error}}' | grep -v '^$$' | head -1); \
			echo -e "  \x1b[96m$$svc\x1b[0m: $${reason:-no reason reported by docker}"; \
		done; \
		echo -e "\nThey are still \x1b[33mup and serving traffic\x1b[0m, but with their \x1b[33mprevious configuration\x1b[0m,"; \
		echo -e "so this deploy has not taken effect for them."; \
		echo -e "\n\x1b[92mIf you did not change any setting or environment variable related to these"; \
		echo -e "services (ex: \x1b[96mCLOUDFLARE_*\x1b[0m/\x1b[96mCF_*\x1b[0m variables for the proxy), you can safely ignore this.\x1b[0m"; \
		echo -e "\nOtherwise, to apply the new configuration:"; \
		echo -e "  1. Check the reason above: a \x1b[33mport conflict\x1b[0m just means the old task still holds the"; \
		echo -e "     published port, and the new one can bind as soon as it exits."; \
		echo -e "     Anything else (resources, placement constraints) must be \x1b[33mfixed first\x1b[0m,"; \
		echo -e "     otherwise the new task will not schedule either."; \
		echo -e "  2. Re-run \x1b[96mRECREATE_STUCK_SERVICES=1 make deploy\x1b[0m to recreate them."; \
		echo -e "     This stops the old container before starting the new one, which"; \
		echo -e "     \x1b[33mbriefly interrupts the traffic they serve\x1b[0m."; \
		if [ -n "$$RECREATE_STUCK_SERVICES" ]; then \
			reply="y"; \
			if [ -t 0 ]; then \
				read -r -p $$'\nRecreate them now? [y/N] ' reply; \
			fi; \
			case "$$reply" in \
				[yY]*) \
					for svc in $$stuck; do \
						echo "Recreating $$svc..."; \
						docker service scale --detach "$$svc"=0 >/dev/null && docker service scale --detach "$$svc"=1 >/dev/null; \
					done; \
					sleep 5; \
					still_stuck=""; \
					for svc in $$stuck; do \
						docker service ps "$$svc" --no-trunc --filter "desired-state=running" --format '{{.CurrentState}}' \
							| grep -q '^Pending' && still_stuck="$$still_stuck $$svc"; \
					done; \
					if [ -n "$$still_stuck" ]; then \
						echo -e "\n\x1b[91m❌ Still pending after being recreated:$$still_stuck\x1b[0m" >&2; \
						echo -e "These services are now \x1b[91mdown\x1b[0m, not stale. Fix the reason docker reported, then run \x1b[96mmake deploy\x1b[0m again." >&2; \
						exit 1; \
					fi; \
					echo -e "\x1b[92mRecreated ✅\x1b[0m"; \
					;; \
				*) \
					echo -e "\nSkipped, the services above are still running their previous configuration."; \
					;; \
			esac; \
		fi; \
	elif [ $$timed_out -eq 1 ]; then \
		echo -e "\n\x1b[91m❌ Deploy timed out after $${deploy_timeout}s and some services never reached their desired state.\x1b[0m" >&2; \
		echo -e "Inspect them with \x1b[96mdocker service ls --filter name=zane_\x1b[0m, or raise the budget with \x1b[96mDEPLOY_TIMEOUT=900 make deploy\x1b[0m." >&2; \
		exit 1; \
	fi; \
	echo -e "\n> You can now access your ZaneOps dashboard at \x1b[96m$$ACCESS_URL\x1b[0m"; \
	echo -e "====== \x1b[94mDONE Deploying ZaneOps ✅\x1b[0m"


deploy-otel: ### Deploy the optional observability stack (Tempo + Grafana on :3004)
	@set -a; . ./.env; set +a; \
	docker stack deploy --detach --with-registry-auth --prune --compose-file docker-stack.prod-otel.yaml zane-otel
	@echo -e "> Observability stack deployed. Set \x1b[96mOTEL_TRACES_ENABLED=true\x1b[0m and \x1b[96mOTEL_EXPORTER_OTLP_ENDPOINT=http://zane.tempo:4317\x1b[0m in .env, then re-run \x1b[96mmake deploy\x1b[0m."

stop-otel: ### Take down the optional observability stack
	@docker stack rm zane-otel

deploy-temporal-ui: ### Deploy the temporal UI stack
	@set -a; . ./.env; set +a; \
	docker stack deploy --detach --with-registry-auth --prune --compose-file docker-stack.prod-temporal-ui.yaml zane-temporal

stop-temporal-ui: ### Take down the temporal UI stack
	@docker stack rm zane-temporal

reset-password: ### Reset user password
	@if [ -z "$(user)" ]; then echo -e "Error: \x1b[33m\$$user\x1b[0m variable is required. Usage: \x1b[96mmake reset-password user=username\x1b[0m"; exit 1; fi
	@docker exec -it $$(docker ps -qf "name=zane_app") /bin/bash -c "source /app/.venv/bin/activate && python manage.py changepassword $(user)"

stop: ### Take down zaneops and scale down all services created in zaneops
	@echo -e "====== \x1b[94mTaking down zaneops...\x1b[0m ======"
	@docker stack rm zane
	@echo -e "Scaling down services created in zaneops..., use \x1b[96mmake deploy\x1b[0m to restart them"
	@docker service ls --filter "label=zane-managed=true" -q | xargs -P 0 -I {} docker service scale --detach {}=0
	@echo -e "====== \x1b[94mDONE ✅\x1b[0m ======"

delete-resources: ### Delete all resources created by zaneops
	@echo -e "====== \x1b[91mDELETING ZaneOps and all its created resources...\x1b[0m ======"
	docker stack rm zane
	@echo "Waiting for all containers related to services to be removed..."
	@while [ -n "$$(docker ps -a | grep "zane_" | awk '{print $$1}')" ]; do \
		sleep 2; \
	done
	@echo "Removing zane-ops volumes..."
	docker volume rm $$(docker volume ls --filter "label=zane.stack=true" -q) || true
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