FROM python:3.12-slim
ARG SETUP_SCRIPT_VERSION
LABEL version="$SETUP_SCRIPT_VERSION"

WORKDIR /usr/src/app
COPY install-docker-prerequisites.sh ./install-docker-prerequisites.sh
COPY setup.py ./setup.py

RUN chmod +x ./install-docker-prerequisites.sh && ./install-docker-prerequisites.sh
RUN apt install -y docker-ce-cli docker-compose-plugin
RUN pip install --no-cache-dir "python-dotenv==1.0.1" "requests==2.32.3" "sentry-sdk"

ENTRYPOINT ["python", "-u", "setup.py"]