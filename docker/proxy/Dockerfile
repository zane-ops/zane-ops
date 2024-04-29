ARG CADDY_VERSION=2.7.6
FROM caddy:${CADDY_VERSION}-builder AS builder

ADD "https://github.com/acouvreur/sablier.git#v1.6.0" /sablier

RUN xcaddy build \
    --with github.com/acouvreur/sablier/plugins/caddy=/sablier/plugins/caddy

FROM caddy:${CADDY_VERSION}

ARG ZANE_HOST=app.zaneops.local
ENV ZANE_HOST=$ZANE_HOST

COPY --from=builder /usr/bin/caddy /usr/bin/caddy
COPY default-caddy-config.json /config/caddy/autosave.json
RUN sed -i "s#{{ZANE_HOST}}#$ZANE_HOST#g" /config/caddy/autosave.json