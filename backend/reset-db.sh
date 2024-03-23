source ./venv/bin/activate && yes | python manage.py flush

# Delete services
docker service rm $(docker service ls -q --filter label=zane-managed=true)

# Delete networks
docker network rm $(docker network ls -q --filter label=zane-managed=true)

# Delete volumes
docker volume rm $(docker volume ls -q --filter label=zane-managed=true)
