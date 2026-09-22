#!/usr/bin/env bash
set -e

# Help function
show_help() {
  cat << EOF
ZaneOps Installation Script

Usage:
  sudo $0 [OPTIONS]

Options:
  -v, --version=VERSION           Set ZaneOps version (default: latest, or 'canary' for main branch)
  -m, --mode=MODE                 Set mode: http or https
  -r, --root-domain=DOMAIN        Set root domain
  -a, --app-domain=DOMAIN         Set app domain
  -d, --app-directory=DIR         Set app directory
      --allow-http-session=BOOL   Enable/disable HTTP session (true/false)
  -h, --help                      Show this help message

Environment Variables:
  VERSION, MODE, ROOT_DOMAIN, APP_DOMAIN, APP_DIRECTORY, ALLOW_HTTP_SESSION
  Note: Command-line arguments take priority over environment variables

Examples:
  # Using named arguments
  sudo $0 --version=v1.2.3 --mode=https --root-domain=example.com

  # Using short flags
  sudo $0 -v v1.2.3 -m https -r example.com

  # Using environment variables
  VERSION=v1.2.3 MODE=https sudo $0

  # Using curl with environment variables
  VERSION=latest curl https://.../install.sh | sudo bash

EOF
  exit 0
}

TOTAL_STEPS=4

# Print a highly visible banner so each step stands out in the logs
print_step() {
    local number="$1"
    local emoji="$2"
    local title="$3"
    local bar="════════════════════════════════════════════════════════════════════"
    local bold="" blue="" reset=""
    if [ -t 1 ]; then
        bold="\033[1m"
        blue="\033[34m"
        reset="\033[0m"
    fi
    echo ""
    printf "%b%s%b\n" "$blue" "$bar" "$reset"
    printf "%b%b  %s  %s  [step %s/%s]%b\n" "$blue" "$bold" "$emoji" "$title" "$number" "$TOTAL_STEPS" "$reset"
    printf "%b%s%b\n" "$blue" "$bar" "$reset"
    echo ""
}

# Check for help flag before anything else
for arg in "$@"; do
  if [ "$arg" = "-h" ] || [ "$arg" = "--help" ]; then
    show_help
  fi
done

# Require root
if [ "$EUID" -ne 0 ]; then
  echo "❌ This script must be run with sudo"
  echo "Run '$0 --help' for usage information"
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

# Defaults applied by `make setup` when nothing is provided (see .env.template)
SSLIP_IP=$(ip route show default 2>/dev/null | awk '/src/ {for (i=1; i<=NF; i++) if ($i=="src") print $(i+1)}' | sed 's/\./-/g')
DEFAULT_SSLIP_DOMAIN="${SSLIP_IP:-127-0-0-1}.sslip.io"
DEFAULT_MODE="https"
DEFAULT_ALLOW_HTTP_SESSION="false"

# Interactively ask for domains if in a terminal and not already provided
if [ -t 0 ] && { [ -z "$ROOT_DOMAIN" ] || [ -z "$APP_DOMAIN" ]; }; then
    echo ""
    echo "🌐 Domain Configuration"
    echo "   ZaneOps needs two domains:"
    echo "   • Root domain : where the ZaneOps dashboard will be accessible (e.g. zane.example.com)"
    echo "   • App domain  : base domain for your deployed apps (e.g. apps.example.com)"
    echo "   Both default to your server's IP via sslip.io — no DNS setup needed."
    echo "   Press Enter or type 'OK' to accept the default value shown in brackets."
    echo ""

    if [ -z "$ROOT_DOMAIN" ]; then
        read -r -p "   Root domain [${DEFAULT_SSLIP_DOMAIN}]: " _input_root
        if [ -z "$_input_root" ] || [ "${_input_root,,}" = "ok" ]; then
            ROOT_DOMAIN="$DEFAULT_SSLIP_DOMAIN"
        else
            ROOT_DOMAIN="$_input_root"
        fi
    fi

    if [ -z "$APP_DOMAIN" ]; then
        read -r -p "   App domain  [${DEFAULT_SSLIP_DOMAIN}]: " _input_app
        if [ -z "$_input_app" ] || [ "${_input_app,,}" = "ok" ]; then
            APP_DOMAIN="$DEFAULT_SSLIP_DOMAIN"
        else
            APP_DOMAIN="$_input_app"
        fi
    fi
    echo ""
fi

if [ "$VERSION" = "canary" ]; then
    echo ""
    echo "⚠️  WARNING: 'canary' tracks the latest commit on main."
    echo "   It is not guaranteed to be bug-free and can break at any time."
    if [ -t 0 ]; then
        read -r -p "   Are you sure you want to continue? [y/N]: " _confirm_canary
        case "$_confirm_canary" in
            [yY]|[yY][eE][sS]) ;;
            *)
                echo "❌ Installation cancelled."
                exit 1
                ;;
        esac
    else
        echo "   Non-interactive session detected: proceeding with canary install."
    fi
    echo ""
fi

# Compute installation directory ahead of the summary so it can be shown to the user
INSTALL_DIR="${APP_DIRECTORY:-/var/www/zaneops}"

echo ""
echo "📋 Installation Summary"
echo "   ZaneOps is a self-hosted, open-source PaaS for deploying web apps, static"
echo "   sites, databases and services — built on Docker Swarm and the Caddy proxy."
echo ""
echo "   This script will:"
echo "   1️⃣  Install the required dependencies (Docker included) if they are missing"
echo "   2️⃣  Initialize a Docker Swarm on this machine"
echo "   3️⃣  Download the ZaneOps Makefile and configure the environment"
echo "   4️⃣  Deploy the ZaneOps stack as a set of Swarm services"
echo ""
echo "   Version              : $VERSION"
echo "   Mode                 : ${MODE:-$DEFAULT_MODE}"
echo "   Root Domain          : ${ROOT_DOMAIN:-$DEFAULT_SSLIP_DOMAIN}"
echo "   App Domain           : ${APP_DOMAIN:-$DEFAULT_SSLIP_DOMAIN}"
echo "   Install Directory    : $INSTALL_DIR"
echo "   Allow HTTP Session   : ${ALLOW_HTTP_SESSION:-$DEFAULT_ALLOW_HTTP_SESSION}"
echo "   Target User          : $ORIGINAL_USER"
echo ""

if [ -t 0 ]; then
    read -r -p "   Proceed with installation? [y/N]: " _confirm_install
    case "$_confirm_install" in
        [yY]|[yY][eE][sS]) ;;
        *)
            echo "❌ Installation cancelled."
            exit 1
            ;;
    esac
else
    echo "   Non-interactive session detected: proceeding without confirmation."
fi
echo ""

print_step 1 "1️⃣" "Checking OS and installing dependencies"

if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    if [ -f /etc/debian_version ]; then
        apt update
        apt install -y make curl jq openssl ca-certificates lsb-release gnupg

        if ! command -v docker &>/dev/null; then
            echo "   ➡️ Installing Docker..."
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
            echo "   ➡️ Installing Docker..."
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
echo "   ➡️ Adding $ORIGINAL_USER to docker group..."
if ! groups "$ORIGINAL_USER" | grep -q '\bdocker\b'; then
    usermod -aG docker "$ORIGINAL_USER"
    echo "   ✅ User $ORIGINAL_USER added to docker group"
    echo "   ⚠️  Note: $ORIGINAL_USER will need to log out and back in for docker group changes to take effect"
else
    echo "   ✅ User $ORIGINAL_USER is already in docker group"
fi

# Initialize Docker Swarm if not already active
print_step 2 "2️⃣" "Initializing Docker Swarm"
if ! docker info 2>/dev/null | grep -q 'Swarm: active'; then
    docker swarm init --advertise-addr 127.0.0.1
else
    echo "   ✅ Docker Swarm is already active"
fi

# Create installation directory, download the Makefile & configure the environment
print_step 3 "3️⃣" "Downloading the Makefile and configuring the environment"
echo "   ➡️ Using INSTALL_DIR=${INSTALL_DIR}"
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

echo "   ➡️ Downloading Makefile..."
curl -sSL https://cdn.zaneops.dev/makefile -o Makefile

# Run setup (creates .env)
echo "   ➡️ Running make setup..."
make setup

# Update .env with custom values
if [ -f .env ]; then
    echo "   ➡️ Configuring .env file..."
    
    # Update IMAGE_VERSION
    echo "      - Setting IMAGE_VERSION to $VERSION..."
    sed -i "s/^IMAGE_VERSION=.*/IMAGE_VERSION=${VERSION}/" .env
    
    # Update MODE if provided
    if [ -n "$MODE" ]; then
        echo "      - Setting MODE to $MODE..."
        sed -i "s/^MODE=.*/MODE='${MODE}'/" .env
    fi
    
    # Update ROOT_DOMAIN if provided
    if [ -n "$ROOT_DOMAIN" ]; then
        echo "      - Setting ROOT_DOMAIN to $ROOT_DOMAIN..."
        sed -i "s/^ROOT_DOMAIN=.*/ROOT_DOMAIN=\"${ROOT_DOMAIN}\"/" .env
    fi
    
    # Update ZANE_APP_DOMAIN if provided
    if [ -n "$APP_DOMAIN" ]; then
        echo "      - Setting ZANE_APP_DOMAIN to $APP_DOMAIN..."
        sed -i "s/^ZANE_APP_DOMAIN=.*/ZANE_APP_DOMAIN=\"${APP_DOMAIN}\"/" .env
    fi
    
    # Update ZANE_APP_DIRECTORY if provided
    if [ -n "$APP_DIRECTORY" ]; then
        echo "      - Setting ZANE_APP_DIRECTORY to $APP_DIRECTORY..."
        sed -i "s|^ZANE_APP_DIRECTORY=.*|ZANE_APP_DIRECTORY=${APP_DIRECTORY}|" .env
    fi
    
    # Update __DANGEROUS_ALLOW_HTTP_SESSION if provided
    if [ -n "$ALLOW_HTTP_SESSION" ]; then
        echo "      - Setting __DANGEROUS_ALLOW_HTTP_SESSION to $ALLOW_HTTP_SESSION..."
        # Check if the line exists (commented or not)
        if grep -q "^#\?__DANGEROUS_ALLOW_HTTP_SESSION=" .env; then
            # Uncomment and update the value
            sed -i "s/^#\?__DANGEROUS_ALLOW_HTTP_SESSION=.*/__DANGEROUS_ALLOW_HTTP_SESSION=${ALLOW_HTTP_SESSION}/" .env
        else
            # Add the line on a new line if it doesn't exist
            echo "" >> .env
            echo "__DANGEROUS_ALLOW_HTTP_SESSION=${ALLOW_HTTP_SESSION}" >> .env
        fi
    fi
else
    echo "   ❌ .env not found after setup!"
    exit 1
fi

# Adjust ownership and deploy
print_step 4 "4️⃣" "Deploying the ZaneOps stack"
echo "   ➡️ Adjusting ownership of $INSTALL_DIR to $ORIGINAL_USER..."
chown -R "$ORIGINAL_USER":"$ORIGINAL_USER" "$INSTALL_DIR"

echo "   ➡️ Running make deploy..."
make deploy