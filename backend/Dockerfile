FROM python:3.11.7-slim

ENV NIXPACKS_VERSION=1.37.0
ENV RAILPACK_VERSION=0.0.64

RUN apt update && apt install -y git \ 
    gcc \
    python3-dev \
    curl \
    htop \
    openssh-client \
    iproute2 \
    && rm -rf /var/lib/apt/lists/*
RUN curl -sSL https://nixpacks.com/install.sh | bash
RUN curl -fsSL https://get.docker.com | sh
RUN curl -sSL https://railpack.com/install.sh | sh

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /code

COPY --from=ghcr.io/astral-sh/uv:0.7.3 /uv /usr/local/bin/uv
ENV UV_SYSTEM_PYTHON=true VIRTUAL_ENV=/opt/.venv

# Place executables in the environment at the front of the path
ENV PATH="/opt/.venv/bin:$PATH"

COPY pyproject.toml .python-version uv.lock ./

RUN uv sync --locked --active

RUN . $VIRTUAL_ENV/bin/activate

COPY . code

EXPOSE 8000

# runs the dev server
CMD bash -c "source /opt/.venv/bin/activate && python manage.py create_metrics_cleanup_schedule && python manage.py runserver"