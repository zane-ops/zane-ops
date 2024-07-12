#!/bin/bash
echo "Removing the proxy and the docker-compose stack..."
docker stack rm zane && docker-compose down --remove-orphans

echo "Scaling down all zane-ops services..."
services=$(docker service ls --filter "label=zane-managed=true" --format "{{.ID}}")
echo "$services" | while IFS= read -r service; do
  if [[ -n "$service" ]]; then
    echo "Scaling down service: $service"
    docker service scale --detach $service=0
  fi
done
echo "Done undeploying the stack"
