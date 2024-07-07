ARG CADDY_VERSION=2.8
FROM caddy:${CADDY_VERSION}-builder AS builder

LABEL org.opencontainers.image.source=https://github.com/zane-ops/zane-ops
LABEL org.opencontainers.image.description="Zaneops proxy build with caddy v2.8"
LABEL org.opencontainers.image.licenses=MIT

RUN xcaddy build \
    --with github.com/caddy-dns/cloudflare

FROM caddy:${CADDY_VERSION}-alpine

ARG ENVIRONMENT=dev

COPY --from=builder /usr/bin/caddy /usr/bin/caddy
COPY default-caddy-config-${ENVIRONMENT}.json /config/caddy/autosave.json