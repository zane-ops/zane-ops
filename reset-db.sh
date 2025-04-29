#!/bin/bash
echo "⚠️ THIS WILL RESET THE DATABASE AND WIPE OUT ALL DATA ⚠️"
read -p "Are you sure? (Y/N): " -n 1 -r

if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    echo "Bye... 👋"
    [[ "$0" = "$BASH_SOURCE" ]] && exit 1 || return 1 # handle exits from shell or function but don't exit interactive shell
fi

echo ""

echo "Deleting all user created services..."
docker service rm $(docker service ls -q --filter label=zane-managed=true)  2>/dev/null

echo "Waiting for all containers related to services to be removed..."
while [ -n "$(docker ps -a | grep "srv-prj_" | awk '{print $1}')" ]; do \
  sleep 2; \
done

echo "Deleting volumes..."
docker volume rm $(docker volume ls -q --filter label=zane-managed=true) 2>/dev/null

echo "Deleting networks..."
docker network rm $(docker network ls -q --filter label=zane-managed=true) 2>/dev/null

echo "Running a system prune..."
docker system prune -f --volumes

echo "Stopping temporal server..."
docker compose -f ./docker/docker-compose.yaml down temporal-server
docker stack rm zane

echo "Flushing temporalio database..."
docker exec -it $(docker ps -qf "name=zane-db") psql -U postgres -c "DROP database temporal;"

echo "Restarting temporal-admin-tools to configure temporal server..."
docker stack deploy --with-registry-auth --compose-file ./docker/docker-stack.yaml zane

echo "Restarting temporalio server..."
docker compose -f ./docker/docker-compose.yaml up -d temporal-server

echo "Resetting caddy config..."
curl "http://127.0.0.1:2019/load" \
	-H "Content-Type: application/json" \
	-d @docker/proxy/default-caddy-config-dev.json

echo "Flushing the main app database..."
source ./backend/.venv/bin/activate && echo yes | SILENT=true python ./backend/manage.py flush


echo "Recreating the superuser..."
source ./backend/.venv/bin/activate && SILENT=true DJANGO_SUPERUSER_USERNAME=admin DJANGO_SUPERUSER_EMAIL=admin@example.com DJANGO_SUPERUSER_PASSWORD=password python ./backend/manage.py createsuperuser --noinput
echo -e "Created a superuser with the credentials \x1b[90musername\x1b[0m=\x1b[94madmin\x1b[0m \x1b[90mpassword\x1b[0m=\x1b[94mpassword\x1b[0m..."
echo "RESET DONE ✅"
