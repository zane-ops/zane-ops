from celery import shared_task


@shared_task
def add(x: int, y: int):
    return x + y
