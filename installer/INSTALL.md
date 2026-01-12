# Streamline Installer

This directory contains scripts that install GMDH Streamline Server with all required components (controller, proxy).

Supported platforms:

- Ubuntu (22.04, 24.04, 24.10)
- mac OS with Docker installed
- WSL (with Docker installed and systemd enabled)

## How to install

If you want to install production versions (latest release and recommended release):

```bash
export STREAMLINE_VERSION=production-latest
curl -fsSL "https://raw.githubusercontent.com/streamlineplan/streamline-install-on-prem/$STREAMLINE_VERSION/installer/bootstrap.sh" | sudo -E bash
```

If you want to install development versions:

```bash
export STREAMLINE_DOCKERHUB_REGISTRY_TOKEN=<dockerhub token>  ## required until our images are public
export STREAMLINE_REPO=streamline-install-on-prem-dev
export STREAMLINE_ENVIRONMENT=development
export STREAMLINE_VERSION=<branch name> # branch of this repo
export STREAMLINE_REPO_USERNAME=<username>  ## your github username
export STREAMLINE_REPO_PASSWORD=<github personal access token>  ## your github personal access token

curl -fsSL -H "Authorization: Bearer $STREAMLINE_REPO_PASSWORD" "https://raw.githubusercontent.com/streamlineplan/$STREAMLINE_REPO/$STREAMLINE_VERSION/installer/bootstrap.sh" | sudo -E bash

```

Additional environment variables:

- `STREAMLINE_CF_TUNNEL_TOKEN` - token for cloudflare tunnel. If provided, tunnel will be setup automatically.
- `STREAMLINE_CONTROLLER_BACKEND_IMAGE` - docker image for controller backend. If not provided, value from default.env will be used.
- `STREAMLINE_CONTROLLER_FRONTEND_IMAGE` - docker image for controller frontend. If not provided, value from default.env will be used.
- `STREAMLINE_CONTROLLER_BACKEND_TAG` - docker image tag for controller backend. If not provided, value from default.env will be used.
- `STREAMLINE_CONTROLLER_FRONTEND_TAG` - docker image tag for controller frontend. If not provided, value from default.env will be used.

---

## Dev notes

Attention: when changing the script, also update the `SETUP_SCRIPT_VERSION` in the `bootstrap.sh` file according to semver rules.
