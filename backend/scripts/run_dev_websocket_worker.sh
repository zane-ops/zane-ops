#!/bin/bash
set -ex 

source $VIRTUAL_ENV/bin/activate 
cd /code && uv sync --locked --active
cd /code && python manage.py runserver --settings=backend.settings_worker 0.0.0.0:$WEBSOCKET_WORKER_PORT