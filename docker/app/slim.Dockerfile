# 1. Build: apt packages
FROM ghcr.io/railwayapp/railpack-builder:latest AS packages-apt-build

RUN apt-get update \
 && apt-get install -y --no-install-recommends libpq-dev python3-dev \
 && rm -rf /var/lib/apt/lists/*

# 2. Build: install mise
FROM packages-apt-build AS packages-mise

ENV MISE_CACHE_DIR=/mise/cache \
    MISE_CONFIG_DIR=/etc/mise \
    MISE_DATA_DIR=/mise \
    MISE_INSTALLS_DIR=/mise/installs \
    MISE_SHIMS_DIR=/mise/shims

# copy python version
COPY ./backend/.python-version .python-version

# write mise.toml
RUN mkdir -p /etc/mise 
COPY ./backend/mise.toml /etc/mise/config.toml

RUN mise trust -a \
 && mise install

RUN mise activate $SHELL

# 3. Build: uv sync
FROM packages-mise AS install

ENV PIP_DEFAULT_TIMEOUT=100 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONFAULTHANDLER=1 \
    PYTHONHASHSEED=random \
    PYTHONUNBUFFERED=1 \
    UV_CACHE_DIR=/opt/uv-cache \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    VIRTUAL_ENV=/app/.venv

WORKDIR /app
COPY ./backend/pyproject.toml ./backend/uv.lock ./

ENV PATH=/root/.local/bin:$PATH

RUN pipx install uv \
 && uv sync --locked --no-dev --no-install-project \
 && uv sync --locked --no-dev --no-editable

# 4. Build: copy source
FROM install AS build

WORKDIR /app
# Copy app static files
COPY ./backend/ /app
COPY ./frontend/build/client/ /app/staticfiles

# Add daphne socket-based configuration
RUN mkdir -p /app/daphne/
RUN chmod -R 777 /app/daphne/

RUN chmod -R a+x /app/scripts/*.sh

# 5. Install Caddy
FROM ghcr.io/railwayapp/railpack-builder:latest AS packages-caddy

RUN mise install-into caddy@2.9.1 /caddy/

# 6. Runtime: packages
FROM debian:bookworm-slim AS packages-runtime

ENV NIXPACKS_VERSION=1.37.0
ENV RAILPACK_VERSION=0.0.64

ENV DEBIAN_FRONTEND=noninteractive

# 1) Install runtime deps & Docker CLI
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates curl gnupg lsb-release \
    && curl -fsSL https://download.docker.com/linux/debian/gpg \
        | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg \
    && echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] \
        https://download.docker.com/linux/debian \
        $(lsb_release -cs) stable" \
        > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        docker-ce-cli \
        docker-buildx-plugin \
        supervisor \
        curl \
        wait-for-it \
        supervisor \
        pkg-config \
        git \
        openssl \
    && rm -rf /var/lib/apt/lists/*

# Add nixpacks and railpack binaries
RUN curl -sSL https://railpack.com/install.sh | sh \
    && curl -sSL https://nixpacks.com/install.sh | bash \
    && rm -rf /var/lib/apt/lists/*

# 7. Final image
FROM packages-runtime

WORKDIR /app

# Ensure all runtime binaries are discoverable
ENV PATH=/caddy:/mise/shims:/app/.venv/bin:$PATH

COPY --from=build /app /app
COPY --from=packages-caddy /caddy/ /caddy/

COPY --from=packages-mise /mise/shims/ /mise/shims/
COPY --from=packages-mise /mise/installs/ /mise/installs/
COPY --from=packages-mise /usr/local/bin/mise /usr/local/bin/mise
COPY --from=packages-mise /etc/mise/config.toml /etc/mise/config.toml
COPY --from=packages-mise /root/.local/state/mise /root/.local/state/mise


# runtime environment variables
ARG COMMIT_SHA
ARG IMAGE_VERSION
ENV COMMIT_SHA=$COMMIT_SHA \
    IMAGE_VERSION=$IMAGE_VERSION \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \ 
    VIRTUAL_ENV=/app/.venv \
    DJANGO_SETTINGS_MODULE=backend.settings \
    NIXPACKS_VERSION=1.37.0 \
    RAILPACK_VERSION=0.0.64

EXPOSE 80

# Start Supervisor
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
