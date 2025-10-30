#!/bin/bash

trap 'exit 0' SIGINT
trap 'exit 0' SIGTERM

# Source .env if it exists
if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi

# Only run if WH_TOKEN is set
if [ -n "$WH_TOKEN" ]; then
  pnpm whcli forward --target=http://localhost:8000
fi