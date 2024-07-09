.DEFAULT_GOAL := help
help: ### Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

setup: ### Launch initial setup before installing zaneops
	echo "⚒️⚒️⚒️⚒️⚒️⚒️⚒️⚒️⚒️⚒️⚒️⚒️⚒️⚒️⚒️⚒️⚒️⚒️⚒️"
	echo "⚒️  INITIAL SETUP OF ZANEOPS  ⚒️"
	echo "⚒️⚒️⚒️⚒️⚒️⚒️⚒️⚒️⚒️⚒️⚒️⚒️⚒️⚒️⚒️⚒️⚒️⚒️⚒️"
	echo "Step 1️⃣ : initiating docker swarm..."
	docker swarm init || true
	echo "Step 1️⃣ Done ✅"
	echo "Step 2️⃣: Preparing the current folder..."
	mkdir -p .fluentd
	chmod a+rw .fluentd
	echo "Step 2️⃣ Done ✅"
	echo "Step 3️⃣: Downloading docker compose files for zaneops..."
	curl https://raw.githubusercontent.com/zane-ops/zane-ops/main/docker/docker-stack.prod.yaml > ./docker-stack.prod.yaml
	curl https://raw.githubusercontent.com/zane-ops/zane-ops/main/docker/docker-stack.prod-http.yaml > ./docker-stack.prod-http.yaml
	curl https://raw.githubusercontent.com/zane-ops/zane-ops/main/docker/attach-proxy-networks.sh > ./attach-proxy-networks.sh
	curl https://raw.githubusercontent.com/zane-ops/zane-ops/main/docker/fluentd/fluent.conf > ./fluent.conf
	chmod a+x ./attach-proxy-networks.sh
	echo "Step 3️⃣ Done ✅"
	echo "Step 4️⃣: Downloading the env file template..."
	curl https://raw.githubusercontent.com/zane-ops/zane-ops/main/.env.example > ./.env.local
	sed -i'.bak' "s#{{INSTALL_DIR}}#$(pwd)#g" ./.env.local
	echo "Step 4️⃣ Done ✅"
	echo "Step 5️⃣: Create docker network for zaneops..."
	docker network create --attachable --driver overlay zane || true
	echo "Step 5️⃣ Done ✅"
	echo "Setup finished 🏁"

deploy: ### Install and deploy zaneops
	echo "🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀"
	echo "🚀   DEPLOYMENT OF ZANEOPS    🚀"
	echo "🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀"
	docker_script="--compose-file docker-stack.prod.yaml"
	read -p "Do you want to be the server through HTTP (recommended if you use a reverse tunnel like cloudflare tunnel) ? (Y/N): " use_http
	if [[ $use_http == [yY] || $confirm == [yY][eE][sS] ]]; then docker_script="--compose-file docker-stack.prod.yaml --compose-file docker-stack.prod-http.yaml";  fi
	set -a; . ./.env.local; set +a && docker stack deploy --with-registry-auth $docker_script zane
	. ./attach-proxy-networks.sh
	echo "Deploy done, Please give this is a little minutes before accessing your website 🏁"
	echo "You can monitor the services deployed by running \`docker service ls --filter label=\"zane.stack=true\"\`"
	echo "Wait for all services to show up as \`replicated   1/1\` to attest that everything started succesfully"

remove: ### Take down zaneops
	echo "Taking down zaneops..."
	docker stack rm zane