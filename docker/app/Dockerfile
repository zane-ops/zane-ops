FROM python:3.11.7-slim

WORKDIR /app

# Install dependencies
RUN apt update && apt install -y --no-install-recommends \
    debian-keyring debian-archive-keyring apt-transport-https curl wait-for-it \
    caddy libpq-dev supervisor gcc python3-dev

# Add Caddy repository and install
RUN curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
RUN echo "deb [signed-by=/usr/share/keyrings/caddy-stable-archive-keyring.gpg] https://dl.cloudsmith.io/public/caddy/stable/debian any-version main" \
    > /etc/apt/sources.list.d/caddy-stable.list

# Environment variables
ARG COMMIT_SHA
ARG IMAGE_VERSION
ENV COMMIT_SHA=${COMMIT_SHA}
ENV IMAGE_VERSION=${IMAGE_VERSION}
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV VIRTUAL_ENV=/venv
ENV DJANGO_SETTINGS_MODULE=backend.settings

# Create and activate virtual environment using uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"  # Add uv to PATH

RUN python -m venv /venv
ENV PATH="/venv/bin:$PATH"

# Copy requirements and install dependencies
COPY ./backend/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY ./backend/ /app
COPY ./frontend/build/client/ /app/staticfiles

# Create directories for logs and sockets
RUN mkdir -p /var/log/caddy /var/log/gunicorn /run/gunicorn
RUN chmod -R 777 /run/gunicorn

# Copy Caddyfile
COPY ./docker/app/Caddyfile /etc/caddy/Caddyfile

# Configure Supervisor
COPY ./docker/app/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Make scripts executable
RUN chmod +x /app/scripts/*.sh

# Expose necessary ports
EXPOSE 80

# Start Supervisor
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
