#!/bin/bash
set -ex 
source $VIRTUAL_ENV/bin/activate 
wait-for-it zane.loki:3100 -t 0 -- wait-for-it zane.temporal:7233 -t 0 -- 
python manage.py run_worker