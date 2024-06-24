ARG CADDY_VERSION=2.8
FROM caddy:${CADDY_VERSION}-builder AS builder


RUN xcaddy build \
    --with github.com/caddy-dns/cloudflare

FROM caddy:${CADDY_VERSION}-alpine

COPY --from=builder /usr/bin/caddy /usr/bin/caddy
COPY default-caddy-config.json /config/caddy/autosave.json