#!/bin/bash
# Building the proxy
echo "Building zane-proxy..."
docker buildx install
docker buildx create --name zane_builder --config ./buildkit/buildkitd.toml --driver=docker-container
echo password | docker login  --username=zane --password-stdin localhost:9989
docker buildx build  --load -t localhost:9989/caddy:2.7.6-with-sablier -t fredkiss3/caddy-with-sablier ./proxy
docker push localhost:9989/caddy:2.7.6-with-sablier
docker push fredkiss3/caddy-with-sablier
