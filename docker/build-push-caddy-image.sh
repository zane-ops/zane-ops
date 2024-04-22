#!/bin/bash
# Building the proxy
echo "Building zane-proxy..."
docker buildx install
docker buildx create --name zane_builder --config ./buildkit/buildkitd.toml --driver=docker-container
echo password | docker login  --username=zane --password-stdin localhost:9989
docker buildx build --push  \
    -t fredkiss3/caddy-with-sablier:latest \
    -t fredkiss3/caddy-with-sablier:v0.1.3 \
    ./proxy
#docker push localhost:9989/caddy:2.7.6-with-sablier
#docker push fredkiss3/caddy-with-sablier:latest
#docker push fredkiss3/caddy-with-sablier:v0.1.0
