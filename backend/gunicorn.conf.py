# -*- coding: utf-8 -*-
import os

workers = int(os.environ.get("GUNICORN_WORKERS", 2))

bind = "0.0.0.0:8000"
loglevel = "info"
