#!/bin/bash

echo "Saving networks attached to the proxy..."
network_id=$(docker network inspect zane_default -f '{{.ID}}')
docker service inspect zane_zane-proxy  | jq --arg network_id "$network_id" '.[].Spec.TaskTemplate.Networks[] | select(.Target != $network_id) | .Target'  > .proxy_attached_networks

echo "Removing the proxy and the docker-compose stack..."
docker stack rm zane && docker-compose down --remove-orphans

echo "Scaling down all zane-ops services..."
services=$(docker service ls  --filter "mode=replicated" --filter "label=zane-managed=true" --format '{{.Name}} {{.Replicas}}' | awk '$2!="0/0" {print $1}')
echo "$services" | while IFS= read -r service; do
  if [[ -n "$service" ]]; then
    echo "Scaling down service: $service"
    docker service scale --detach $service=0
    # Add your commands for each service here
  fi
done
echo "$services" > .alive_services

echo "Done undeploying the stack"
