#!/usr/bin/env bash
set -e

# Detect OS and install required packages
echo "Installing required packages..."
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    if [ -f /etc/debian_version ]; then
        sudo apt update
        sudo apt install -y make curl jq openssl docker.io
    elif [ -f /etc/redhat-release ]; then
        sudo dnf install -y make curl jq openssl docker
    elif [ -f /etc/alpine-release ]; then
        sudo apk add make curl jq openssl docker
    elif [ -f /etc/arch-release ]; then
        sudo pacman -S --noconfirm make curl jq openssl docker
    else
        echo "Unsupported Linux distribution"
        exit 1
    fi
elif [[ "$OSTYPE" == "darwin"* ]]; then
    brew install make curl jq openssl docker
else
    echo "Unsupported OS: $OSTYPE"
    exit 1
fi

# Initialize Docker Swarm
echo "Initializing Docker Swarm on 127.0.0.1..."
docker swarm init --advertise-addr 127.0.0.1 || echo "Swarm already initialized"

# Create installation directory
INSTALL_DIR="/var/www/zaneops"
echo "Creating installation directory at $INSTALL_DIR..."
sudo mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

# Download Makefile
echo "Downloading Makefile..."
curl -sSL https://cdn.zaneops.dev/makefile -o Makefile

# Run setup and deploy
echo "Running setup and deploy..."
make setup
make deploy

echo "ZaneOps installation complete! Access the dashboard at http://127-0-0-1.sslip.io"
