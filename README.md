# Self-hosted Deployment of Streamline

This repository contains Docker Compose configurations and install scripts for deploying self-hosted Streamline. It provides a complete setup for running the application stack locally or in a private infrastructure.

For installation instructions, please refer to [INSTALL.md](installer/INSTALL.md).

## Overview

Streamline consists of four main components:

1. **Portainer** - A container management UI that allows you to manage your Docker containers, images, networks, and volumes through a web interface.

2. **Traefik** - A reverse proxy that provides external access to components of system. For example, main streamline app is accesible on path `/`, controller frontend is accessible on path `/admin/ui`.

3. **Controller** - A management system that controls deployment of most other components.

   - Frontend - A web interface for managing Streamline
  
   - Backend
  
   - WUD (what's up docker) - A tool for updating Portainer
  
4. **Streamline Stack** - The core application stack that includes:

   - Engine Server
  
   - Web Server
  
   - Cloudflare Tunnel (optional) for secure external access
  
5. **Backups** - Automated backup system for Docker volumes using Azure Storage or other storages

System uses a shared network (`streamline-network`) to enable communication between all containers. 
Volume (`streamline-data`) used for storing data of most components.


## Support
For issues or questions, please refer to the Streamline documentation or contact your system administrator.