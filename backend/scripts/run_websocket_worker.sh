#!/bin/bash
set -ex 

source $VIRTUAL_ENV/bin/activate 
daphne -b 0.0.0.0 -p $WEBSOCKET_WORKER_PORT backend.worker_asgi:application