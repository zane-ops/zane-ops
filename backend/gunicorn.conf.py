# -*- coding: utf-8 -*-
# Use as much workers as there are CPUs available
import multiprocessing

workers = multiprocessing.cpu_count()

bind = "0.0.0.0:8000"
loglevel = "info"
