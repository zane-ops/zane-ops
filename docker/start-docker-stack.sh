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
docker stack deploy --with-registry-auth --compose-file ./docker-stack.yaml zane

echo "Scaling up all zane-ops services..."
# File containing the services to scale up
docker service ls --filter "label=zane-managed=true" --filter "label=status=active" -q |  xargs -P 0 -I {} docker service scale --detach {}=1

# Wait until Ctrl+C is pressed
echo -e "Server launched at \x1b[96mhttp://localhost:5173/\x1b[0m"
echo "Press Ctrl+C to stop everything..."
while true; do
  sleep 1
done
