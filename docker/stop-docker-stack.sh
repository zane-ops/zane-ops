#!/bin/bash

echo "Saving networks attached to the proxy..."
network_id=$(docker network inspect zane_default -f '{{.ID}}')
docker service inspect zane_zane-proxy  | jq --arg network_id "$network_id" '.[].Spec.TaskTemplate.Networks[] | select(.Target != $network_id) | .Target'  > .proxy_attached_networks

echo "Removing the proxy and the docker-compose stack..."
docker stack rm zane && docker-compose down --remove-orphans

echo "Scaling down all zane-ops services..."
services=$(docker service ls --filter label=zane-managed=true --format "{{.Name}}")
for service in $services; do
  docker service scale --detach $service=0
done
echo "Done undeploying the stack"
