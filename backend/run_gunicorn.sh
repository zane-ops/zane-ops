#!/bin/bash
set -ex 
wait-for-it zane.search:9200 -t 0 -- wait-for-it zane.temporal:7233 -t 0 -- 
/venv/bin/python manage.py migrate 
/venv/bin/python manage.py create_log_cleanup_schedule 
/venv/bin/gunicorn --config=/app/gunicorn.conf.py backend.wsgi:application