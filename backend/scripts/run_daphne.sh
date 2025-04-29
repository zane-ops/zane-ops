#!/bin/bash
set -ex 
wait-for-it zane.loki:3100 -t 0 -- wait-for-it zane.temporal:7233 -t 0 -- 
source $VIRTUAL_ENV/bin/activate
python manage.py migrate 
python manage.py create_metrics_cleanup_schedule 
python manage.py create_system_cleanup_schedule
daphne -u /app/daphne/daphne.sock backend.asgi:application