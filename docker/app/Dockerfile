FROM python:3.11.7-slim

WORKDIR /app

# Install dependencies
RUN apt update && apt install -y debian-keyring debian-archive-keyring apt-transport-https  curl wait-for-it 
RUN curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
RUN curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
RUN apt update && apt install -y caddy libpq-dev supervisor gcc python3-dev


# environment variables
ARG COMMIT_SHA
ENV COMMIT_SHA=$COMMIT_SHA
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV VIRTUAL_ENV=/venv
ENV DJANGO_SETTINGS_MODULE=backend.settings

# start the venv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
RUN ~/.local/bin/uv venv /venv
COPY ./backend/requirements.txt requirements.txt
RUN  ~/.local/bin/uv pip install -r requirements.txt

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

# Start Supervisor
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]

