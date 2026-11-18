#!/bin/bash
set -ex 
wait-for-it zane.loki:3100 -t 0 -- wait-for-it zane.temporal:7233 -t 0 -- 

source $VIRTUAL_ENV/bin/activate 
cd /code && uv sync --locked --active
python /code/manage.py watch_worker --watch /code