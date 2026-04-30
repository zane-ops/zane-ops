#!/bin/sh
set -e

# Generate pgbouncer.ini from env
cat > /etc/pgbouncer/pgbouncer.ini << EOF
[databases]
zane = host=${DB_HOST:-zane.db} port=${DB_PORT:-5432} dbname=zane
temporal = host=${DB_HOST:-zane.db} port=${DB_PORT:-5432} dbname=temporal
temporal_visibility = host=${DB_HOST:-zane.db} port=${DB_PORT:-5432} dbname=temporal_visibility


[pgbouncer]
listen_addr = 0.0.0.0
listen_port = 5432
auth_type   = ${AUTH_TYPE:-scram-sha-256}
auth_file   = /etc/pgbouncer/userlist.txt
pool_mode   = ${POOL_MODE:-transaction}
max_db_connections = ${MAX_DB_CONNECTIONS:-100}
default_pool_size  = ${DEFAULT_POOL_SIZE:-50}
EOF

# Generate userlist.txt from env
echo "\"${DB_USER}\" \"${DB_PASSWORD}\"" > /etc/pgbouncer/userlist.txt

exec pgbouncer /etc/pgbouncer/pgbouncer.ini