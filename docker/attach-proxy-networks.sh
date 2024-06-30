#!/bin/bash

echo "Attaching saved networks to the proxy..."
# Service name or ID
service_name="zane_zane-proxy"

# File containing the new network IDs
file=".proxy_attached_networks"

if [ ! -f $file ]; then
    echo "No saved network found."
    exit 0
fi

# Read and prepare network IDs from the file
while read p; do
  net_id=$(echo $p | sed 's/"//g')
  if [ -n "$net_id" ]; then
   docker service update --network-add $net_id $service_name
  fi
done <$file

