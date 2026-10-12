#!/bin/bash
set -ex 
wait-for-it zane.loki:3100 -t 0 -- wait-for-it zane.temporal:7233 -t 0 -- 

source $VIRTUAL_ENV/bin/activate 
uv sync --locked --active
watchmedo auto-restart --directory=/code --pattern=*.py --ignore-patterns="/code/**/tests/**" --recursive -- python manage.py run_worker
