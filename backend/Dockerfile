FROM python:3.11.7-slim

RUN apt update && apt install -y git gcc python3-dev curl

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN pip install uv==0.4.2
RUN uv venv /venv
COPY requirements.txt requirements.txt
ENV VIRTUAL_ENV=/venv
RUN uv pip install -r requirements.txt

COPY . code
WORKDIR /code

EXPOSE 8000

# runs the dev server
CMD bash -c "source /venv/bin/activate && uv pip install -r requirements.txt && python manage.py create_metrics_cleanup_schedule && python manage.py runserver"