source ./backend/venv/bin/activate && echo yes | python ./backend/manage.py flush

echo "Scaling down all zane-ops services..."
services=$(docker service ls --filter label=zane-managed=true --format "{{.Name}}")
for service in $services; do
  docker service scale --detach $service=0
done

echo "Deleting services..."
docker service rm $(docker service ls -q --filter label=zane-managed=true)  2>/dev/null

echo "Deleting volumes..."
docker volume rm $(docker volume ls -q --filter label=zane-managed=true) 2>/dev/null

echo "Deleting networks..."
docker network rm $(docker network ls -q --filter label=zane-managed=true) 2>/dev/null

# Reset caddy config
sed -i .bak "s#{{ZANE_HOST}}#zane.local#g" ./docker/proxy/default-caddy-config.json

curl "http://localhost:2019/load" \
	-H "Content-Type: application/json" \
	-d @docker/proxy/default-caddy-config.json

rm ./docker/proxy/default-caddy-config.json
mv ./docker/proxy/default-caddy-config.json.bak ./docker/proxy/default-caddy-config.json