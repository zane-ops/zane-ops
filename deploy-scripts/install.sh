#!/usr/bin/env bash
set -e

# Require root
if [ "$EUID" -ne 0 ]; then
  echo "❌ This script must be run with sudo:"
  echo "   sudo $0 --version=<version> --mode=<mode> --root-domain=<domain> --app-domain=<domain> --app-directory=<dir> --allow-http-session=<true|false>"
  echo "   sudo $0 -v <version> -m <mode> -r <domain> -a <domain> -d <dir> --allow-http-session <true|false>"
  echo "   VERSION=<version> MODE=<mode> ROOT_DOMAIN=<domain> APP_DOMAIN=<domain> APP_DIRECTORY=<dir> ALLOW_HTTP_SESSION=<true|false> sudo $0"
  echo "   VERSION=<version> curl https://.../install.sh | sudo bash"
  exit 1
fi

# Remember original user
ORIGINAL_USER=${SUDO_USER:-$USER}

# Parse named arguments
for arg in "$@"; do
  case $arg in
    --version=*|-v=*)
      CLI_VERSION="${arg#*=}"
      shift
      ;;
    --mode=*|-m=*)
      CLI_MODE="${arg#*=}"
      shift
      ;;
    --root-domain=*|-r=*)
      CLI_ROOT_DOMAIN="${arg#*=}"
      shift
      ;;
    --app-domain=*|-a=*)
      CLI_APP_DOMAIN="${arg#*=}"
      shift
      ;;
    --app-directory=*|-d=*)
      CLI_APP_DIRECTORY="${arg#*=}"
      shift
      ;;
    --allow-http-session=*)
      CLI_ALLOW_HTTP_SESSION="${arg#*=}"
      shift
      ;;
    -v|--version|-m|--mode|-r|--root-domain|-a|--app-domain|-d|--app-directory|--allow-http-session)
      # Handle space-separated arguments
      flag="$arg"
      shift
      value="$1"
      case $flag in
        -v|--version)
          CLI_VERSION="$value"
          ;;
        -m|--mode)
          CLI_MODE="$value"
          ;;
        -r|--root-domain)
          CLI_ROOT_DOMAIN="$value"
          ;;
        -a|--app-domain)
          CLI_APP_DOMAIN="$value"
          ;;
        -d|--app-directory)
          CLI_APP_DIRECTORY="$value"
          ;;
        --allow-http-session)
          CLI_ALLOW_HTTP_SESSION="$value"
          ;;
      esac
      shift
      ;;
    *)
      # Unknown option
      ;;
  esac
done

# Prioritize: CLI args > env vars > defaults
VERSION="${CLI_VERSION:-${VERSION:-latest}}"
MODE="${CLI_MODE:-${MODE}}"
ROOT_DOMAIN="${CLI_ROOT_DOMAIN:-${ROOT_DOMAIN}}"
APP_DOMAIN="${CLI_APP_DOMAIN:-${APP_DOMAIN}}"
APP_DIRECTORY="${CLI_APP_DIRECTORY:-${APP_DIRECTORY}}"
ALLOW_HTTP_SESSION="${CLI_ALLOW_HTTP_SESSION:-${ALLOW_HTTP_SESSION}}"

echo "➡️ Installing ZaneOps version: $VERSION"
[ -n "$MODE" ] && echo "➡️ Mode: $MODE"
[ -n "$ROOT_DOMAIN" ] && echo "➡️ Root Domain: $ROOT_DOMAIN"
[ -n "$APP_DOMAIN" ] && echo "➡️ App Domain: $APP_DOMAIN"
[ -n "$APP_DIRECTORY" ] && echo "➡️ App Directory: $APP_DIRECTORY"
[ -n "$ALLOW_HTTP_SESSION" ] && echo "➡️ Allow HTTP Session: $ALLOW_HTTP_SESSION"

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
if ! groups "$ORIGINAL_USER" | grep -q '\bdocker\b'; then
    usermod -aG docker "$ORIGINAL_USER"
    echo "✅ User $ORIGINAL_USER added to docker group"
    echo "⚠️  Note: $ORIGINAL_USER will need to log out and back in for docker group changes to take effect"
else
    echo "✅ User $ORIGINAL_USER is already in docker group"
fi

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

# Run setup (creates .env)
echo "➡️ Running make setup..."
make setup

# Update .env with custom values
if [ -f .env ]; then
    echo "➡️ Configuring .env file..."
    
    # Update IMAGE_VERSION
    echo "  - Setting IMAGE_VERSION to $VERSION..."
    sed -i "s/^IMAGE_VERSION=.*/IMAGE_VERSION=${VERSION}/" .env
    
    # Update MODE if provided
    if [ -n "$MODE" ]; then
        echo "  - Setting MODE to $MODE..."
        sed -i "s/^MODE=.*/MODE='${MODE}'/" .env
    fi
    
    # Update ROOT_DOMAIN if provided
    if [ -n "$ROOT_DOMAIN" ]; then
        echo "  - Setting ROOT_DOMAIN to $ROOT_DOMAIN..."
        sed -i "s/^ROOT_DOMAIN=.*/ROOT_DOMAIN=\"${ROOT_DOMAIN}\"/" .env
    fi
    
    # Update ZANE_APP_DOMAIN if provided
    if [ -n "$APP_DOMAIN" ]; then
        echo "  - Setting ZANE_APP_DOMAIN to $APP_DOMAIN..."
        sed -i "s/^ZANE_APP_DOMAIN=.*/ZANE_APP_DOMAIN=\"${APP_DOMAIN}\"/" .env
    fi
    
    # Update ZANE_APP_DIRECTORY if provided
    if [ -n "$APP_DIRECTORY" ]; then
        echo "  - Setting ZANE_APP_DIRECTORY to $APP_DIRECTORY..."
        sed -i "s|^ZANE_APP_DIRECTORY=.*|ZANE_APP_DIRECTORY=${APP_DIRECTORY}|" .env
    fi
    
    # Update __DANGEROUS_ALLOW_HTTP_SESSION if provided
    if [ -n "$ALLOW_HTTP_SESSION" ]; then
        echo "  - Setting __DANGEROUS_ALLOW_HTTP_SESSION to $ALLOW_HTTP_SESSION..."
        # Check if the line exists (commented or not)
        if grep -q "^#\?__DANGEROUS_ALLOW_HTTP_SESSION=" .env; then
            # Uncomment and update the value
            sed -i "s/^#\?__DANGEROUS_ALLOW_HTTP_SESSION=.*/__DANGEROUS_ALLOW_HTTP_SESSION=${ALLOW_HTTP_SESSION}/" .env
        else
            # Add the line if it doesn't exist
            echo "\n__DANGEROUS_ALLOW_HTTP_SESSION=${ALLOW_HTTP_SESSION}" >> .env
        fi
    fi
else
    echo "❌ .env not found after setup!"
    exit 1
fi

# Adjust ownership and deploy
echo "➡️ Adjusting ownership of $INSTALL_DIR to $ORIGINAL_USER..."
chown -R "$ORIGINAL_USER":"$ORIGINAL_USER" "$INSTALL_DIR"

echo "➡️ Running make deploy..."
make deploy