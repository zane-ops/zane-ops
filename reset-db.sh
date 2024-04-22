#!/bin/bash
read -p "Are you sure? (Y/N): " -n 1 -r
echo    # (optional) move to a new line
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    echo "Bye... 👋"
    [[ "$0" = "$BASH_SOURCE" ]] && exit 1 || return 1 # handle exits from shell or function but don't exit interactive shell
fi


echo "Flushing the database..."
source ./backend/venv/bin/activate && echo yes | python ./backend/manage.py flush

echo "Scaling down all zane-ops services..."
services=$(docker service ls --filter label=zane-managed=true --format "{{.Name}}")
for service in $services
do
  docker service scale $service=0
done
echo "Waiting for 5 seconds for the services to to finish scaling down..."
sleep 5

echo "Deleting services..."
docker service rm $(docker service ls -q --filter label=zane-managed=true)  2>/dev/null

echo "Deleting volumes..."
docker volume rm $(docker volume ls -q --filter label=zane-managed=true) 2>/dev/null

echo "Detaching networks from the proxy..."

zane_networks_ids=$(docker network ls -q --filter label=zane-managed=true --format '{{.ID}}')
network_options=""
while read -r net_id;
do
  network_options+=" --network-rm $net_id"
done <<< "$zane_networks_ids"

service_name="zane_zane-proxy"
echo "docker service update $network_options zane_zane-proxy"
if [ -n "$network_options" ]; then
    # Update the service with all networks
    docker service update $network_options $service_name
fi

echo "Deleting networks..."
docker network rm $(docker network ls -q --filter label=zane-managed=true) 2>/dev/null

echo "Resetting caddy config..."
sed -i'.bak' "s#{{ZANE_HOST}}#app.zaneops.local#g" ./docker/proxy/default-caddy-config.json

curl "http://localhost:2019/load" \
	-H "Content-Type: application/json" \
	-d @docker/proxy/default-caddy-config.json

rm ./docker/proxy/default-caddy-config.json
mv ./docker/proxy/default-caddy-config.json.bak ./docker/proxy/default-caddy-config.json

echo "Recreating the superuser..."
source ./backend/venv/bin/activate && python ./backend/manage.py createsuperuser