#!/bin/bash
echo "⚠️ THIS WILL RESET THE DATABASE AND WIPE OUT ALL DATA ⚠️"
read -p "Are you sure? (Y/N): " -n 1 -r

if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    echo "Bye... 👋"
    [[ "$0" = "$BASH_SOURCE" ]] && exit 1 || return 1 # handle exits from shell or function but don't exit interactive shell
fi

echo ""

# always run from the repo root
cd "$(dirname "${BASH_SOURCE[0]}")" || exit 1

wait_for() {
  # usage: wait_for "<description>" <command...>
  local description=$1
  shift
  local tries=0
  until "$@" >/dev/null 2>&1; do
    tries=$((tries + 1))
    if [ $tries -ge 90 ]; then
      echo "❌ Timed out waiting for $description"
      exit 1
    fi
    sleep 2
  done
}

no_containers_for_services() {
  for id in "$@"; do
    [ -n "$(docker ps -aq --filter "label=com.docker.swarm.service.id=$id")" ] && return 1
  done
  return 0
}

no_zane_stack_left() {
  [ -z "$(docker service ls -q --filter label=com.docker.stack.namespace=zane)" ] &&
  [ -z "$(docker ps -aq --filter label=com.docker.stack.namespace=zane)" ] &&
  [ -z "$(docker network ls -q --filter label=com.docker.stack.namespace=zane)" ]
}

echo "Deleting all user created services..."
SERVICE_IDS=$(docker service ls -q --filter label=zane-managed=true)
if [ -n "$SERVICE_IDS" ]; then
  docker service rm $SERVICE_IDS >/dev/null
  echo "Waiting for all containers related to services to be removed..."
  wait_for "user services containers to be removed" no_containers_for_services $SERVICE_IDS
fi

echo "Removing the zane stack (proxy, temporal, vector)..."
docker stack rm zane
wait_for "the zane stack to be removed" no_zane_stack_left

echo "Deleting volumes..."
docker volume rm $(docker volume ls -q --filter label=zane-managed=true) 2>/dev/null

echo "Deleting networks..."
docker network rm $(docker network ls -q --filter label=zane-managed=true) 2>/dev/null

echo "Running a system prune..."
docker system prune -f --volumes

echo "Flushing temporalio database..."
docker exec -it $(docker ps -qf "name=zane-db") psql -U postgres -c "DROP database temporal;"

echo "Redeploying the zane stack..."
if [ -f ./docker/.env ]; then
  (set -a; . ./docker/.env; set +a; docker stack deploy --with-registry-auth --detach=true --compose-file ./docker/docker-stack.yaml zane)
else
  docker stack deploy --with-registry-auth --detach=true --compose-file ./docker/docker-stack.yaml zane
fi

source ./backend/.venv/bin/activate

echo "Unapplying all migrations of the main app database..."
for app in $(SILENT=true python ./backend/manage.py showmigrations | grep -v '^ '); do
  SILENT=true python ./backend/manage.py migrate "$app" zero --noinput || exit 1
done

echo "Reapplying all migrations..."
SILENT=true python ./backend/manage.py migrate --noinput || exit 1

echo "Waiting for temporal to be ready & recreating the automated schedules..."
wait_for "temporal to be ready" env SILENT=true python ./backend/manage.py setup_automated_schedules

echo "RESET DONE ✅"
