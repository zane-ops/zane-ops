#!/bin/bash

echo "Attaching saved networks to the proxy..."
# Service name or ID
service_name="zane_zane-proxy"

# File containing the new network IDs
file=".proxy_attached_networks"

# Read and prepare network IDs from the file
network_options=""
while read p; do
  net_id=$(echo $p | sed 's/"//g')
  network_options+=" --network-add $net_id"
done <$file
if [ -n "$network_options" ]; then
    # Update the service with all networks
    docker service update $network_options $service_name
fi

