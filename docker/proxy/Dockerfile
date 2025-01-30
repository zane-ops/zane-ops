FROM ghcr.io/fredkiss3/caddy-cloudflare:2.8.4-alpine

LABEL org.opencontainers.image.source=https://github.com/zane-ops/zane-ops

ARG COMMIT_SHA
ENV COMMIT_SHA=$COMMIT_SHA
ARG ENVIRONMENT=dev

RUN apk update && apk add --no-cache curl jq

COPY default-caddy-config-${ENVIRONMENT}.json /config/caddy/autosave.json
CMD caddy run --resume