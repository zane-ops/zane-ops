ARG CADDY_VERSION=2.8
FROM caddy:${CADDY_VERSION}-builder AS builder

LABEL org.opencontainers.image.source=https://github.com/zane-ops/zane-ops

RUN xcaddy build \
    --with github.com/caddy-dns/cloudflare

FROM caddy:${CADDY_VERSION}-alpine

ARG ENVIRONMENT=dev

RUN apk add --no-cache wget

COPY --from=builder /usr/bin/caddy /usr/bin/caddy
COPY default-caddy-config-${ENVIRONMENT}.json /config/caddy/autosave.json
CMD caddy run --resume