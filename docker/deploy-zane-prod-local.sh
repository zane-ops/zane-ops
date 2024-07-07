#!/bin/bash

export IMAGE_VERSION=alpha
export ZANE_APP_DIRECTORY=$(pwd)
export ZANE_DB_USER=zane
export ZANE_DB_PASSWORD=password

docker stack deploy --detach=false --compose-file ./docker-stack-prod.yaml zane-prod