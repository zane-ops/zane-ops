FROM python:3.11.7-slim

ENV NIXPACKS_VERSION=1.37.0
ENV RAILPACK_VERSION=0.0.64

RUN apt update && apt install -y git gcc python3-dev curl htop
RUN curl -sSL https://nixpacks.com/install.sh | bash
RUN curl -fsSL https://get.docker.com | sh
RUN curl -sSL https://railpack.com/install.sh | sh

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /code

ENV VIRTUAL_ENV=/code/.venv
RUN pip install uv==0.4.2
COPY pyproject.toml uv.lock ./
RUN uv sync --locked

COPY . code

EXPOSE 8000

# runs the dev server
CMD bash -c "source /code/.venv/bin/activate && python manage.py create_metrics_cleanup_schedule && python manage.py runserver"