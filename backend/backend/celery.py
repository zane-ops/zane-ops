import os

from celery import Celery
from celery.signals import task_postrun

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")

app = Celery("backend")

app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django apps.
app.autodiscover_tasks()


@task_postrun.connect
def after_task_run(signal, sender, retval, task_id, state, args, kwargs, **other):
    print(f"TASK FINISHED RUNNING ({task_id})")
    print(f"retval={retval}")
    print(f"task_id={task_id}")
    print(f"args={args}")
    print(f"kwargs={kwargs}")
    print(f"state={state}")


# @task_prerun.connect
# def after_task_run(signal, sender, task_id, args, kwargs, **other):
#     print(f"TASK STARTING RUNNING ({task_id})")
#     print(f"task_id={task_id}")
#     print(f"args={args}")
#     print(f"kwargs={kwargs}")


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
