#!/usr/bin/env bash
# Detect the distribution
if [ -f /etc/os-release ]; then
    . /etc/os-release
    DISTRO=$ID
else
    echo "Error: Cannot detect distribution"
    exit 1
fi

# Validate supported distributions
case $DISTRO in
    ubuntu|debian)
        echo "Detected supported distribution: $DISTRO"
        ;;
    *)
        echo "Error: Unsupported distribution: $DISTRO"
        exit 1
        ;;
esac

apt-get update -y
apt-get install -y ca-certificates curl gnupg lsb-release
mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/$DISTRO/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/$DISTRO $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    | tee /etc/apt/sources.list.d/docker.list > /dev/null
apt-get update -y