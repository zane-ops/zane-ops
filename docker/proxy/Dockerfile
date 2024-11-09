FROM ghcr.io/fredkiss3/caddy-cloudflare:2.8.4-alpine

LABEL org.opencontainers.image.source=https://github.com/zane-ops/zane-ops

RUN apk add --no-cache curl

COPY default-caddy-config-${ENVIRONMENT}.json /config/caddy/autosave.json
CMD caddy run --resume