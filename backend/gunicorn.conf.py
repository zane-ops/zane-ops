# -*- coding: utf-8 -*-
import os

workers = int(os.environ.get("GUNICORN_WORKERS", 2))

bind = "unix:/run/gunicorn/gunicorn.sock"
loglevel = "info"
timeout = 120
