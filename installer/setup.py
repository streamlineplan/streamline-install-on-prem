#!/usr/bin/env python3
import argparse
from dataclasses import dataclass
import os
import random
import re
import requests
import string
import subprocess
import sys
import time
import sentry_sdk

from urllib.parse import quote
from pwd import getpwnam
from dotenv import dotenv_values

INSTALLER_REPO_PATH = "/installer-repo"

PORTAINER_STACK_NAME = "streamline-portainer"
CONTROLLER_STACK_NAME = "streamline-controller"
TRAEFIK_STACK_NAME = "streamline-traefik"
TRAEFIK_SERVICE_NAME = "traefik"
TRAEFIK_PORT = 80

PORTAINER_COMPOSE_PATH = "compose/portainer/compose.yml"
CONTROLLER_COMPOSE_PATH = "compose/controller/compose.yml"
CONTROLLER_COMPOSE_ENV_PATH = "compose/controller/default.env"
TRAEFIK_ENV_PATH = "compose/traefik/default.env"

PORTAINER_ADMIN_PASSWORD_FILE = f"/.portainer-admin-pwd.txt"
PORTAINER_REGISTRY_NAME = "gmdhstreamline"

DOCKERHUB_REGISTRY_NAME = "gmdhstreamline"
DOCKERHUB_REGISTRY_USERNAME = "gmdhstreamline"

LOCAL_PORTAINER_ENDPOINT_ID = None  # Will be set dynamically
PORTAINER_ENDPOINT_CREATION_TYPE = 1
DOCKERHUB_REGISTRY_TYPE = 6  ## Portainer constant for DockerHub registry

# Status symbols
SUCCESS = "✓ "
WARNING = "! "
ERROR = "⨉ "

def ensure_root():
    """Ensure the script is run as root."""
    if os.geteuid() != 0:
        print(f"{ERROR}This script must be run as root. Please use sudo.")
        sys.exit(1)
    
def read_or_generate_portainer_password(password_file):
    """Get or generate Portainer admin password."""
    if os.path.isfile(password_file) and os.path.getsize(password_file) > 0:
        # Read existing password from file
        with open(password_file, 'r') as f:
            password = f.read().strip()
        print(f"Using existing password from {password_file}")
        return password
    
    # Generate random password
    chars = string.ascii_letters + string.digits + '!@#$%^&*()-_=+'
    password = ''.join(random.choice(chars) for _ in range(20))
    
    # Save new password to file
    os.makedirs(os.path.dirname(password_file), exist_ok=True)
    with open(password_file, 'w') as f:
        f.write(password)
    print(f"{SUCCESS}Created admin password and saved to {password_file}")
    return password

def init_portainer_admin(portainer_url, password):
    """Initialize Portainer admin user."""
    print(f"Initializing Portainer admin user...")

    response = requests.post(
        f"{portainer_url}/api/users/admin/init",
        json={"username": "admin", "password": password},
    )    
    response.raise_for_status()
    print(f"{SUCCESS}Portainer admin user initialized!")

def authenticate_with_portainer(portainer_url, password):
    """Authenticate with Portainer API and get JWT token."""
    print(f"Authenticating with Portainer API...")
        
    response = requests.post(
        f"{portainer_url}/api/auth",
        json={"username": "admin", "password": password}
    )
    response.raise_for_status()
    
    # Extract JWT token from response
    auth_data = response.json()
    jwt_token = auth_data.get('jwt')
    
    if not jwt_token:
        print(f"{ERROR}Failed to extract JWT token from Portainer API response")
        print(f"{ERROR}Response: {response.text}")
        sys.exit(1)
    
    print(f"{SUCCESS}Successfully authenticated with Portainer API")
    return jwt_token

def run_command(cmd, env={}):
    """Run a command and handle exceptions, showing error output."""
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True, env=os.environ | env)
        return result
    except subprocess.CalledProcessError as e:
        print(f"{ERROR}Command '{e.cmd}' failed with return code {e.returncode}")
        if e.stdout:
            print(f"Command stdout:\n{e.stdout}")
        if e.stderr:
            print(f"Command stderr:\n{e.stderr}")
        sys.exit(1)


def setup_dockerhub_registry(portainer_url, jwt_token, dockerhub_token):
    response = requests.get(f"{portainer_url}/api/registries", headers={
        "Authorization": f"Bearer {jwt_token}"
    })
    response.raise_for_status()

    registry_exists = any(registry.get('Name') == PORTAINER_REGISTRY_NAME for registry in response.json())
    if registry_exists:
        print(f"{SUCCESS}Dockerhub registry already exists in Portainer")
        return
    print(f"Creating registry in Portainer...")
    response = requests.post(
        f"{portainer_url}/api/registries",
        headers={
        "Authorization": f"Bearer {jwt_token}"
        },
        json={
            "type": DOCKERHUB_REGISTRY_TYPE,
            "name": PORTAINER_REGISTRY_NAME,
            "url": "docker.io",
            "username": DOCKERHUB_REGISTRY_USERNAME,
            "password": dockerhub_token,
            "authentication": True
        }
    )
    response.raise_for_status()
    print(f"{SUCCESS}Dockerhub registry created in Portainer")

def setup_portainer():
    """Setup and configure Portainer."""    
    # Start Portainer
    print(f"Starting Portainer...")
    run_command([
        "docker", "compose", "-p", PORTAINER_STACK_NAME, 
        "-f", f"{INSTALLER_REPO_PATH}/compose/portainer/compose.yml", 
        "up", 
        "--detach", "--wait", "--pull", "always"
    ])
    
    portainer_url = f"http://portainer:9000"

    print(f"{SUCCESS}Portainer deployed at http://localhost:9984")
    print(f"Checking if Portainer admin credentials exist...")
    
    # Check admin status using requests
    response = requests.get(f"{portainer_url}/api/users/admin/check")
        
    # If Portainer returns a 303 status code, restart the container and try again
    if response.status_code == 303:
        print(f"Portainer will be restarted to set admin password.")
        run_command(["docker", "compose", "-p", PORTAINER_STACK_NAME, "restart"])
        print(f"{SUCCESS}Portainer restarted!")
        time.sleep(1)
        
        print(f"Retrying admin check...")
        response = requests.get(f"{portainer_url}/api/users/admin/check")
            
    # Process based on HTTP status code
    if response.ok:
        print("Portainer admin credentials already exist")
        if not os.path.isfile(PORTAINER_ADMIN_PASSWORD_FILE):
            print(f"{ERROR}Portainer admin password file does not exist at {PORTAINER_ADMIN_PASSWORD_FILE}. Please reset password in Portainer and rerun the script.")
            sys.exit(1)
        
        with open(PORTAINER_ADMIN_PASSWORD_FILE, 'r') as f:
            password = f.read().strip()
        
        if not password:
            print(f"{ERROR}Portainer admin password file is empty. Please reset password in Portainer and rerun the script.")
            sys.exit(1)
    else:
        print("Portainer admin credentials don't exist, creating new credentials...")
        password = read_or_generate_portainer_password(PORTAINER_ADMIN_PASSWORD_FILE)
        init_portainer_admin(portainer_url, password)
    
    # Authenticate with Portainer API and get JWT token
    jwt_token = authenticate_with_portainer(portainer_url, password)

    dockerhub_token = os.getenv("STREAMLINE_DOCKERHUB_REGISTRY_TOKEN")
    if dockerhub_token is not None:
        print(f"Dockerhub token provided, setting up dockerhub registry in Portainer...")
        setup_dockerhub_registry(portainer_url, jwt_token, dockerhub_token)
    else:
        print(f"Dockerhub token not provided, skipping dockerhub registry setup")

    ensure_portainer_endpoint_exists(portainer_url, jwt_token)
    
    return portainer_url, jwt_token


def env_file_to_portainer_json(env_file_path: str):
    env_vars = dotenv_values(env_file_path)
    return [{"name": key, "value": value} for key, value in env_vars.items()]
    

def ensure_portainer_endpoint_exists(portainer_url, jwt_token):
    global LOCAL_PORTAINER_ENDPOINT_ID
    
    print(f"Checking if local Portainer environment exists...")

    endpoint_response = requests.get(
        f"{portainer_url}/api/endpoints?name=local",
        headers={
            "Authorization": f"Bearer {jwt_token}"
        }
    )
    endpoint_response.raise_for_status()
    endpoints = endpoint_response.json()
    
    if len(endpoints) > 0:
        # Found existing endpoint with name=local, use its ID
        LOCAL_PORTAINER_ENDPOINT_ID = str(endpoints[0]["Id"])
        print(f"Local environment found with id {LOCAL_PORTAINER_ENDPOINT_ID}")
    else:
        print("Local Portainer environment not found, will be created")
        
        create_response = requests.post(
            f"{portainer_url}/api/endpoints?Name=local&EndpointCreationType={PORTAINER_ENDPOINT_CREATION_TYPE}",
            headers={
                "Authorization": f"Bearer {jwt_token}",
                "Content-Type": "application/json"
            }
        )
        if not create_response.ok:
            print(f"{ERROR}Error creating environment: HTTP {create_response.status_code}")
            print(f"{ERROR}Response: {create_response.text}")
            sys.exit(1)
        
        # Extract the ID from the created endpoint
        created_endpoint = create_response.json()
        LOCAL_PORTAINER_ENDPOINT_ID = str(created_endpoint["Id"])
        print(f"{SUCCESS}Local environment created with id {LOCAL_PORTAINER_ENDPOINT_ID}")

@dataclass
class EnvMapping:
    local_env: str
    controller_env: str
    should_be_logged: bool

def deploy_controller_stack(portainer_url, jwt_token):
    """Deploy controller stack."""
    # Check if the stack already exists in Portainer
    print(f"Checking if controller stack already exists...")
    
    response = requests.get(
        f"{portainer_url}/api/stacks",
        headers={
            "Authorization": f"Bearer {jwt_token}"
        }
    )
    response.raise_for_status()
    
    stacks_data = response.json()
    stack_id = None
    for stack in stacks_data:
        if stack.get('Name') == CONTROLLER_STACK_NAME:
            stack_id = stack.get('Id')
            break
    
    # Delete the existing stack if it exists
    if stack_id is not None:
        print(f"{WARNING}Stack {CONTROLLER_STACK_NAME} will be redeployed, all envs overrides will be lost")
        print(f"Deleting existing stack {CONTROLLER_STACK_NAME}...")
        
        delete_response = requests.delete(
            f"{portainer_url}/api/stacks/{stack_id}?endpointId={LOCAL_PORTAINER_ENDPOINT_ID}",
            headers={
                "Authorization": f"Bearer {jwt_token}"
            },
            timeout=None
        )
        delete_response.raise_for_status()
        print(f"{SUCCESS}Existing stack deleted")
    else:
        print("Controller stack not found and will be deployed")
            
    envs = env_file_to_portainer_json(f"{INSTALLER_REPO_PATH}/compose/controller/default.env")

    def add_or_update_env(envs_list, name, value):
        for env in envs_list:
            if env["name"] == name:
                env["value"] = value
                return
        envs_list.append({"name": name, "value": value})

    add_or_update_env(envs, "CONTROLLER_STACK_NAME", CONTROLLER_STACK_NAME)

    env_mappings = [
        EnvMapping("STREAMLINE_ENVIRONMENT", "FRONTEGG_ENVIRONMENT", True),
        EnvMapping("STREAMLINE_CONTROLLER_BACKEND_IMAGE", "CONTROLLER_BACKEND_IMAGE", True),
        EnvMapping("STREAMLINE_CONTROLLER_FRONTEND_IMAGE", "CONTROLLER_FRONTEND_IMAGE", True),
        EnvMapping("STREAMLINE_CONTROLLER_BACKEND_TAG", "CONTROLLER_BACKEND_TAG", True),
        EnvMapping("STREAMLINE_CONTROLLER_FRONTEND_TAG", "CONTROLLER_FRONTEND_TAG", True),
        EnvMapping("STREAMLINE_REPO_USERNAME", "MANIFESTS_GIT_REPO_USERNAME", False),
        EnvMapping("STREAMLINE_REPO_PASSWORD", "MANIFESTS_GIT_REPO_PASSWORD", False),
        EnvMapping("STREAMLINE_REPO", "MANIFESTS_GIT_REPO_SLUG", True),
        EnvMapping("STREAMLINE_CF_TUNNEL_TOKEN", "SETUP_CF_TOKEN_AT_STARTUP", False)
    ]
    
    print(f"Using following environment variables overrides for controller stack:")
    for mapping in env_mappings:
        value = os.getenv(mapping.local_env)
        if value is not None:
            add_or_update_env(envs, mapping.controller_env, value)
            print(f"{mapping.controller_env}: {value if mapping.should_be_logged else '<hidden>'}")

    username = os.getenv("STREAMLINE_REPO_USERNAME")
    password = os.getenv("STREAMLINE_REPO_PASSWORD")

    repo_url = f"https://{username + "@" if username is not None else ''}github.com/streamlineplan/{os.getenv("STREAMLINE_REPO")}.git"
    print(f"Git repository URL: {repo_url}")
        
    has_credentials = username is not None and password is not None
    # Prepare the request body
    request_body = {
        "name": CONTROLLER_STACK_NAME,
        "composeFile": CONTROLLER_COMPOSE_PATH,
        "env": envs,
        "repositoryURL": repo_url,
        "repositoryReferenceName": f"refs/heads/{os.getenv("STREAMLINE_VERSION")}",
        "repositoryAuthentication": has_credentials,
        "tlsskipVerify": False
    }

    if has_credentials:
        request_body["repositoryUsername"] = os.getenv("STREAMLINE_REPO_USERNAME")
        request_body["repositoryPassword"] = os.getenv("STREAMLINE_REPO_PASSWORD")
    
    # Deploy controller stack
    print(f"Deploying controller stack...")
    
    deploy_response = requests.post(
        f"{portainer_url}/api/stacks/create/standalone/repository?endpointId={LOCAL_PORTAINER_ENDPOINT_ID}",
        headers={
            "Authorization": f"Bearer {jwt_token}",
        },
        json=request_body
    )
    deploy_response.raise_for_status()

    print(f"{SUCCESS}Controller stack deployed successfully")


def wait_for_controller_ready(controller_url):
    """Wait for the controller to be ready by checking for 2xx response."""
    print(f"Waiting for controller to be ready...")
    MAX_WAIT_TIME = 300  # 5 minutes
    start_time = time.time()
    while time.time() - start_time < MAX_WAIT_TIME:
        try:
            response = requests.get(controller_url, timeout=2)
            if 200 <= response.status_code < 300:
                print(f"{SUCCESS}Controller is ready!")
                return
        except requests.exceptions.RequestException:
            # Continue waiting if request fails
            pass
        time.sleep(0.5)  # Wait 500 ms between checks
    print(f"{ERROR}Controller failed to become ready within {MAX_WAIT_TIME} seconds. Please try re-running the install script.")
    sys.exit(1)

## We expect traefik port to be forwarded to port from default.env, but in future installer may need to get actual port from deployed stack
def get_default_traefik_forwarded_port() -> str:
    TRAEFIK_ENV_PATH=f"{INSTALLER_REPO_PATH}/compose/traefik/default.env"
    return dotenv_values(TRAEFIK_ENV_PATH)["FORWARDED_PORT"]

def get_controller_frontend_path() -> str:
    CONTROLLER_ENV_PATH=f"{INSTALLER_REPO_PATH}/compose/controller/default.env"
    return dotenv_values(CONTROLLER_ENV_PATH)["CONTROLLER_FRONTEND_URL_PATH"]

def main():
    try:
        sentry_sdk.init(
            dsn="https://114c8b6e903dae8659fd1f9cbfd472a8@o4505629035266048.sentry-ingest.streamlineplan.com/4509401138069504",
            environment=None,
            traces_sample_rate=.0,
            release=f"streamline-linux-installer@{os.getenv('SETUP_SCRIPT_VERSION', 'unknown')}",
            send_default_pii=True
        )

        ensure_root()

        portainer_url, jwt_token = setup_portainer()
        
        deploy_controller_stack(portainer_url, jwt_token)

        controller_frontend_path = get_controller_frontend_path()
        wait_for_controller_ready(f"http://{TRAEFIK_SERVICE_NAME}:{TRAEFIK_PORT}/{controller_frontend_path}")

        proxy_forwarded_port = get_default_traefik_forwarded_port()
        controller_external_url = f"http://localhost:{proxy_forwarded_port}{controller_frontend_path}"
        print(f"{SUCCESS}Controller is available at {controller_external_url}")
        
        print(f"{SUCCESS}GMDH Streamline Server installation completed successfully!")

    except requests.exceptions.HTTPError as e:
        print(f"{ERROR}HTTP error occurred: {e}")
        print(f"{ERROR}Response body: {e.response.text}")
        sys.exit(1)


if __name__ == "__main__":
    main() 