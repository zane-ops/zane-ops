#!/bin/bash

# Function to undeploy the stack
cleanup() {
  echo "Undeploying the stack..."
  source ./stop-docker-stack.sh
  exit 0
}

# Trap SIGINT (Ctrl+C) and call the cleanup function
trap cleanup SIGINT
trap cleanup SIGTERM

# Deploy the stack
echo "Deploying the stack..."
docker-compose down --remove-orphans
docker-compose up -d --remove-orphans

echo "Launching the proxy..."
docker stack deploy --with-registry-auth --compose-file ./docker-stack.yaml zane
source ./attach-proxy-networks.sh


echo "Scaling up all zane-ops services..."

# File containing the services to scale up
exclude_label="zane-allow-sleeping=true"
services=$(docker service ls --filter "label=zane-managed=true" --format "{{.ID}}" | xargs -I {} sh -c 'docker service inspect {} | grep -q "'$exclude_label'" || echo {}')
echo "$services" | while IFS= read -r service; do
  if [[ -n "$service" ]]; then
    echo "Scaling down service: $service"
    docker service scale --detach $service=1
  fi
done

# Wait until Ctrl+C is pressed
echo "Server launched at http://app.127-0-0-1.sslip.io/"
echo "Press Ctrl+C to stop everything..."
while true; do
  sleep 1
done
