import os

from celery import Celery
from celery.signals import task_postrun, task_prerun, setup_logging

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")

app = Celery("backend")

app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django apps.
app.autodiscover_tasks()


@task_postrun.connect
def after_task_run(signal, sender, retval, task_id, state, args, kwargs, **other):
    from django.conf import settings

    if state == "FAILURE" or settings.DEBUG:
        print(f"==============================")
        print(f"AFTER TASK RUN ({task_id})")
        print(f"retval={retval}")
        print(f"task_id={task_id}")
        print(f"args={args}")
        print(f"kwargs={kwargs}")
        print(f"state={state}")
        print(f"==============================\n")


@task_prerun.connect
def before_task_run(signal, sender, task_id, args, kwargs, **other):
    from django.conf import settings

    if settings.DEBUG:
        print(f"==============================")
        print(f"BEFORE TASK RUN ({task_id})")
        print(f"task_id={task_id}")
        print(f"args={args}")
        print(f"kwargs={kwargs}")
        print(f"==============================\n")


@setup_logging.connect
def config_loggers(*args, **kwargs):
    from logging.config import dictConfig
    from django.conf import settings

    dictConfig(settings.LOGGING)


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
