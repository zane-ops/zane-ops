FROM python:3.11.7-slim

RUN apt update && yes | apt install gcc python3-dev

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
CMD uv venv /venv && python manage.py runserver