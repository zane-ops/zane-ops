FROM python:3.11.7-slim

WORKDIR /app

# Install dependencies
RUN apt install -y debian-keyring debian-archive-keyring apt-transport-https  curl
RUN curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
RUN curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
RUN apt update && apt install -y caddy libpq-dev supervisor gcc python3-dev

# Create a non-root user
RUN useradd -m zane
RUN chown -R zane:zane /app
USER zane

# environment variables
ARG COMMIT_SHA
ENV COMMIT_SHA=$COMMIT_SHA
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN pip install uv==0.4.2
ENV VIRTUAL_ENV=/venv
RUN uv venv /venv
COPY requirements.txt requirements.txt
RUN uv pip install -r requirements.txt

# Copy app static files
COPY ./backend /app
COPY ./frontend/dist/ /app/staticfiles

# Add Gunicorn socket-based configuration
RUN mkdir -p /run/gunicorn/
RUN chmod -R 777 /run/gunicorn/
ENV DJANGO_SETTINGS_MODULE=backend.settings


# Configure Supervisor
COPY ./docker/app/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY ./docker/app/Caddyfile /etc/caddy/Caddyfile

RUN chmod a+x /app/run_gunicorn.sh

# Expose necessary ports
EXPOSE 80

# Start Supervisor
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]

