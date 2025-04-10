
FROM kkv66yjemff:bbc9230e166edf6b6fe36b395ea505945fec85a7-builder AS source

# Webapp based on caddy
FROM caddy:2-alpine AS production

WORKDIR /srv

# `/app/` is the output directory of nixpacks files
COPY --from=source /app/dist/ /srv/ 
# COPY ./Caddyfile /etc/caddy/Caddyfile
