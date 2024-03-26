#!/bin/bash

# Function to undeploy the stack
cleanup() {
  echo "Undeploying the stack..."
  source ./stop-docker-stack.sh
  exit 0
}

# Trap SIGINT (Ctrl+C) and call the cleanup function
trap cleanup SIGINT

# Deploy the stack
echo "Deploying the stack..."
docker-compose down --remove-orphans
docker-compose up -d --remove-orphans

# Building the proxy
echo "Building zane-proxy..."
docker buildx install
docker buildx create --name zane_builder --config ./buildkit/buildkitd.toml --driver=docker-container
echo password | docker login  --username=zane --password-stdin localhost:9989
docker buildx build  --load -t localhost:9989/caddy:2.7.6-with-sablier ./proxy
docker push localhost:9989/caddy:2.7.6-with-sablier

echo "Launching the proxy..."
docker stack deploy --with-registry-auth --compose-file ./docker-stack.yaml zane
source ./attach-proxy-networks.sh

echo "Scaling up all zane-ops services..."
services=$(docker service ls --filter label=zane-managed=true --format "{{.Name}}")
for service in $services; do
  if [ "$service"  != "zane_zane-proxy" ]; then
    docker service scale --detach $service=1
  fi
done

# Wait until Ctrl+C is pressed
echo "Press Ctrl+C to undeploy the stack..."
while true; do
  sleep 1
done
