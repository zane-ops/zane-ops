source ./backend/venv/bin/activate && yes | python ./backend/manage.py flush

# Delete services
docker service rm $(docker service ls -q --filter label=zane-managed=true)

# Delete networks
docker network rm $(docker network ls -q --filter label=zane-managed=true)

# Delete volumes
docker volume rm $(docker volume ls -q --filter label=zane-managed=true)

# Reset caddy config
sed -i .bak "s#{{ZANE_HOST}}#$ZANE_HOST#g" ./docker/proxy/default-caddy-config.json

curl "http://localhost:2019/load" \
	-H "Content-Type: application/json" \
	-d @docker/proxy/default-caddy-config.json

rm ./docker/proxy/default-caddy-config.json
mv ./docker/proxy/default-caddy-config.json.bak ./docker/proxy/default-caddy-config.json