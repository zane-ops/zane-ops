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
docker service ls --filter "label=zane-managed=true" --filter "label=status=active" -q |  xargs -P 0 -I {} docker service scale --detach {}=1

# Wait until Ctrl+C is pressed
echo "Server launched at http://localhost:5678/"
echo "Press Ctrl+C to stop everything..."
while true; do
  sleep 1
done
