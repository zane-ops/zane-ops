#!/bin/bash
set -ex 
source /venv/bin/activate 
wait-for-it zane.search:9200 -t 0 -- wait-for-it zane.temporal:7233 -t 0 -- 
python manage.py run_worker