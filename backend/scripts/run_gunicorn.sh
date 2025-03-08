#!/bin/bash
set -ex 
wait-for-it zane.search:9200 -t 0 -- wait-for-it zane.temporal:7233 -t 0 -- 
source /venv/bin/activate
python manage.py migrate 
python manage.py create_metrics_cleanup_schedule 
python manage.py create_system_cleanup_schedule
gunicorn --config=/app/gunicorn.conf.py backend.wsgi:application