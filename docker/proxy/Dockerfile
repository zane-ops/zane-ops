FROM ghcr.io/fredkiss3/caddy-cloudflare:2.8.4-alpine

LABEL org.opencontainers.image.source=https://github.com/zane-ops/zane-ops

ARG COMMIT_SHA
ENV COMMIT_SHA=${COMMIT_SHA}
ARG ENVIRONMENT=dev

# Update and install necessary packages
RUN apk update && apk add --no-cache curl jq

# Copy Caddy configuration file
COPY default-caddy-config-${ENVIRONMENT}.json /config/caddy/autosave.json

# Set permissions for the Caddy config directory
RUN chown -R caddy:caddy /config/caddy

# Start Caddy
USER caddy
CMD caddy run --resume
