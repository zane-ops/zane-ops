#!/usr/bin/env bash
set -e

# Require root
if [ "$EUID" -ne 0 ]; then
  echo "❌ This script must be run with sudo:"
  echo "   sudo $0"
  exit 1
fi

# Remember original user
ORIGINAL_USER=${SUDO_USER:-$USER}

echo "➡️ Checking OS and installing dependencies..."

if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    if [ -f /etc/debian_version ]; then
        apt update
        apt install -y make curl jq openssl ca-certificates lsb-release gnupg

        if ! command -v docker &>/dev/null; then
            echo "➡️ Installing Docker..."
            install -m 0755 -d /etc/apt/keyrings
            curl -fsSL https://download.docker.com/linux/$(. /etc/os-release && echo "$ID")/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
            echo \
              "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/$(. /etc/os-release && echo "$ID") \
              $(lsb_release -cs) stable" > /etc/apt/sources.list.d/docker.list
            apt update
            apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
        fi
        systemctl enable --now docker

    elif [ -f /etc/redhat-release ]; then
        dnf install -y make curl jq openssl yum-utils
        if ! command -v docker &>/dev/null; then
            echo "➡️ Installing Docker..."
            dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
            dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
        fi
        systemctl enable --now docker

    elif [ -f /etc/alpine-release ]; then
        apk add --no-cache make curl jq openssl docker
        rc-update add docker boot
        service docker start

    elif [ -f /etc/arch-release ]; then
        pacman -Syu --noconfirm make curl jq openssl docker
        systemctl enable --now docker

    else
        echo "❌ Unsupported Linux distribution"
        exit 1
    fi

elif [[ "$OSTYPE" == "darwin"* ]]; then
    echo "⚠️ macOS detected. Please install Docker Desktop manually."
    brew install make curl jq openssl || true

else
    echo "❌ Unsupported OS: $OSTYPE"
    exit 1
fi

# Add user to docker group
echo "➡️ Adding $ORIGINAL_USER to docker group..."
usermod -aG docker "$ORIGINAL_USER"

# Create installation directory
INSTALL_DIR="/var/www/zaneops"
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

# Initialize Docker Swarm if not already active
if ! docker info 2>/dev/null | grep -q 'Swarm: active'; then
    echo "➡️ Initializing Docker Swarm on 127.0.0.1..."
    docker swarm init --advertise-addr 127.0.0.1
fi

# Download Makefile
echo "➡️ Downloading Makefile..."
curl -sSL https://cdn.zaneops.dev/makefile -o Makefile

# Run setup and deploy with logs
echo "➡️ Running make setup..."
make setup
echo "➡️ Adjusting ownership of $INSTALL_DIR to $ORIGINAL_USER..."
chown -R "$ORIGINAL_USER":"$ORIGINAL_USER" "$INSTALL_DIR"

echo "➡️ Running make deploy..."
make deploy
