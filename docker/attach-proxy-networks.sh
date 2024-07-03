#!/bin/bash

echo "Attaching saved networks to the proxy..."
network_ids=$(docker network ls --filter "label=zane-managed=true" -q)
for network_id in $network_ids;
do
  if [ -n "$network_id" ]; then
    docker service update --network-add "$network_id" zane_zane-proxy
  fi
done

