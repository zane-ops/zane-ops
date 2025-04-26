FROM python:3.11.7-slim AS base


# Install dependencies
RUN apt update && apt install -y debian-keyring debian-archive-keyring apt-transport-https  curl wait-for-it && rm -rf /var/lib/apt/lists/*
RUN curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
RUN curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
RUN apt update && apt install -y caddy libpq-dev supervisor gcc python3-dev git && rm -rf /var/lib/apt/lists/*
RUN curl -sSL https://nixpacks.com/install.sh | bash
RUN curl -fsSL https://get.docker.com | sh
RUN curl -sSL https://railpack.com/install.sh | sh

# environment variables
ARG COMMIT_SHA
ARG IMAGE_VERSION
ENV COMMIT_SHA=$COMMIT_SHA
ENV IMAGE_VERSION=$IMAGE_VERSION
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV VIRTUAL_ENV=/venv
ENV DJANGO_SETTINGS_MODULE=backend.settings

# start the venv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
RUN ~/.local/bin/uv venv /venv
COPY ./backend/requirements.txt requirements.txt
RUN  ~/.local/bin/uv pip install -r requirements.txt

RUN apt clean -y && apt remove -y --purge gcc libpq-dev python3-dev libgcc-12-dev && apt autoremove -y 

# Copy app static files
COPY ./backend/ /app
COPY ./frontend/build/client/ /app/staticfiles

# Add Gunicorn socket-based configuration
RUN mkdir -p /run/gunicorn/
RUN chmod -R 777 /run/gunicorn/

RUN chmod -R a+x /app/scripts/*.sh

# Configure Supervisor
COPY ./docker/app/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY ./docker/app/Caddyfile /etc/caddy/Caddyfile

# Expose necessary ports
EXPOSE 80

RUN mkdir -p /app/logs/caddy
RUN mkdir -p /app/logs/gunicorn

FROM python:3.11.7-slim AS production

WORKDIR /app

# environment variables
ARG COMMIT_SHA
ARG IMAGE_VERSION
ENV COMMIT_SHA=$COMMIT_SHA
ENV IMAGE_VERSION=$IMAGE_VERSION
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV VIRTUAL_ENV=/venv
ENV DJANGO_SETTINGS_MODULE=backend.settings

COPY --from=base / /

# Start Supervisor
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]

