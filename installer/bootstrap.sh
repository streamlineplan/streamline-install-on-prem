#!/usr/bin/env bash

set -e

# Store original arguments before parsing
ORIGINAL_ARGS="$@"

# Check if version parameter was provided
if [ -z "$STREAMLINE_VERSION" ]; then
    echo "Error: STREAMLINE_VERSION environment variable is required"
    exit 1
fi

# Check if repo parameter was provided, set default if not
if [ -z "$STREAMLINE_REPO" ]; then
    STREAMLINE_REPO="streamline-install-on-prem"
    echo "STREAMLINE_REPO not set, using default: $STREAMLINE_REPO"
fi

# Export the variable so setup.sh can access it
export STREAMLINE_REPO

echo "Downloading installation files..."

if [ -n "$STREAMLINE_REPO_PASSWORD" ]; then
    curl -fsSL -o /tmp/$STREAMLINE_REPO.tar.gz -H "Authorization: Bearer $STREAMLINE_REPO_PASSWORD" https://api.github.com/repos/streamlineplan/$STREAMLINE_REPO/tarball/$STREAMLINE_VERSION
else
    curl -fsSL -o /tmp/$STREAMLINE_REPO.tar.gz https://api.github.com/repos/streamlineplan/$STREAMLINE_REPO/tarball/$STREAMLINE_VERSION
fi
mkdir -p /tmp/$STREAMLINE_REPO
tar -xzf /tmp/$STREAMLINE_REPO.tar.gz -C /tmp/$STREAMLINE_REPO/ --strip-components=1

echo "Running setup..."

# Change to installer directory and run setup
cd /tmp/$STREAMLINE_REPO/installer

chmod +x ./setup.sh

./setup.sh $ORIGINAL_ARGS

rm /tmp/$STREAMLINE_REPO.tar.gz
rm -rf /tmp/$STREAMLINE_REPO

