FROM ghcr.io/fredkiss3/caddy-cloudflare:2.8.4-alpine

LABEL org.opencontainers.image.source=https://github.com/zane-ops/zane-ops

ARG ENVIRONMENT=dev

RUN apk add --no-cache wget

COPY --from=builder /usr/bin/caddy /usr/bin/caddy
COPY default-caddy-config-${ENVIRONMENT}.json /config/caddy/autosave.json
CMD caddy run --resume