#!/usr/bin/env bash
set -e

export SETUP_SCRIPT_VERSION="3.0.0"

INSTALL_DIR="/var/lib/gmdh-streamline-server"
mkdir -p "$INSTALL_DIR"

# Redirect all output to both stdout and a log file
TIMESTAMP=$(date "+%Y-%m-%d %H:%M:%S")
echo "\n\n----- New installation (v$SETUP_SCRIPT_VERSION) ($TIMESTAMP) -----" >> "$INSTALL_DIR/installation.log"
exec > >(tee -a "$INSTALL_DIR/installation.log") 2>&1

# Ensure the script is run as root
if [ "$EUID" -ne 0 ]; then
    echo "Error: This script must be run as root. Please use sudo."
    exit 1
fi

# Detect operating system
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    OS="macos"
    echo "Detected macOS"
elif [ -f /etc/os-release ]; then
    # Linux
    source /etc/os-release
    if [ "$ID" = "ubuntu" ]; then
        OS="ubuntu"
        # Supported Ubuntu versions (per Docker docs)
        SUPPORTED_VERSIONS=("22.04" "24.04" "24.10")
        version_supported=false
        if [[ " ${SUPPORTED_VERSIONS[*]} " == *" $VERSION_ID "* ]]; then
            version_supported=true
        fi

        if [ "$version_supported" = false ]; then
            echo "Error: Current Ubuntu version ($VERSION_ID) is not supported."
            exit 1
        fi
        echo "Current Ubuntu version ($VERSION_ID) is supported."

        # Ensure systemd is installed
        if ! command -v systemd >/dev/null 2>&1; then
            echo "Error: systemd is not installed. This script requires systemd to be present."
            exit 1
        fi
    else
        echo "Error: Only Ubuntu is supported on Linux systems."
        exit 1
    fi
else
    echo "Error: Unable to detect operating system."
    exit 1
fi

# Set environment variables for non-interactive installation
export DEBIAN_FRONTEND=noninteractive
export TZ=UTC

chmod +x ./install-docker-prerequisites.sh
# Check if Docker is already installed
if command -v docker >/dev/null 2>&1; then
    echo "✓ Docker is already installed. Skipping Docker installation."
else
    if [ "$OS" = "ubuntu" ]; then
        echo "→ Docker is not installed. Proceeding with installation..."
        ./install-docker-prerequisites.sh
        # Install Docker Engine and the Docker Compose plugin (Compose v2)
        apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
        echo "✓ Docker installed successfully."
    else
        echo "Error: Autoinstallation of Docker Engine is not supported on $OS. Please install Docker manually and re-run the installer."
        exit 1
    fi
fi

if [ "$OS" = "ubuntu" ]; then
    # Add the non-root user to the docker group (if not already a member)
    if ! getent group docker >/dev/null; then
        groupadd docker
        echo "✓ Created 'docker' group"
    fi

    # Only add user to docker group if SUDO_USER is defined
    if [ -n "$SUDO_USER" ]; then
        if id -nG "$SUDO_USER" | grep -qw docker; then
            echo "✓ User $SUDO_USER is already in the docker group."
        else
            usermod -aG docker "$SUDO_USER"
            echo "✓ User $SUDO_USER has been added to the docker group. To use docker without sudo, please log out and log back in."
        fi
    fi
fi

echo "docker version details:"
docker --version
docker compose version

## Running setup.py in container to avoid installing python and other dependencies on host

echo "Building installer image..."
docker build --build-arg SETUP_SCRIPT_VERSION=$SETUP_SCRIPT_VERSION -t gmdh-streamline-installer -f ./installer.Dockerfile .

# Create the Docker network if it doesn't exist
if ! docker network inspect streamline-network >/dev/null 2>&1; then
    docker network create streamline-network
    echo "✓ Docker network streamline-network created successfully."
else
    echo "✓ Docker network streamline-network already exists."
fi

# Create the Portainer admin password file and make it writable for the user
PORTAINER_ADMIN_PASSWORD_FILE="${INSTALL_DIR}/.portainer-admin-pwd.txt"

touch $PORTAINER_ADMIN_PASSWORD_FILE
chmod 666 $PORTAINER_ADMIN_PASSWORD_FILE

# Create temporary env file for STREAMLINE_ variables
TEMP_ENV_FILE=$(mktemp)
env | grep '^STREAMLINE_' > "$TEMP_ENV_FILE"

docker run --rm \
  -v $(pwd)/..:/installer-repo:ro \
  -v $PORTAINER_ADMIN_PASSWORD_FILE:/.portainer-admin-pwd.txt \
  -v /var/run/docker.sock:/var/run/docker.sock \
  --network streamline-network \
  --env SETUP_SCRIPT_VERSION=$SETUP_SCRIPT_VERSION \
  --env-file "$TEMP_ENV_FILE" \
  gmdh-streamline-installer \
  "$@"

# Clean up temporary env file
rm -f "$TEMP_ENV_FILE"

docker image rm gmdh-streamline-installer >/dev/null 2>&1

# Set ownership for the portainer admin password file to the sudo caller and ensure user 999 (controller backend) can read it
if [ -n "$SUDO_USER" ]; then
    # Get the sudo caller's group
    SUDO_USER_GROUP=$(id -gn "$SUDO_USER")
    chown $SUDO_USER:$SUDO_USER_GROUP $PORTAINER_ADMIN_PASSWORD_FILE
    
    # Set permissions: owner read/write, group read, others read (so user 999 can read)
    chmod 644 $PORTAINER_ADMIN_PASSWORD_FILE
    
    # Additionally, use setfacl if available to explicitly grant read access to user 999
    if command -v setfacl >/dev/null 2>&1; then
        setfacl -m u:999:r $PORTAINER_ADMIN_PASSWORD_FILE 2>/dev/null || true
    fi
else
    # Fallback if SUDO_USER is not available
    chown $USER:$USER $PORTAINER_ADMIN_PASSWORD_FILE
    chmod 644 $PORTAINER_ADMIN_PASSWORD_FILE
fi