FROM python:3.11-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
      bash \
      ca-certificates \
      curl \
      gnupg \
      iproute2 \
      iputils-ping \
      netcat-openbsd \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc \
    && chmod a+r /etc/apt/keyrings/docker.asc \
    && . /etc/os-release \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian ${VERSION_CODENAME} stable" > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends docker-ce-cli docker-compose-plugin \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV DASHBOARD_REPO_ROOT=/repo
ENV DASHBOARD_HOST=0.0.0.0
ENV DASHBOARD_PORT=8000

EXPOSE 8000

# `exec` replaces the shell so uvicorn becomes PID 1 and receives SIGTERM directly.
# Without it the shell stays PID 1, never forwards the signal, and every stop waits out
# the full Docker grace period before being SIGKILLed (exit 137).
CMD ["sh", "-c", "exec uvicorn main:app --host ${DASHBOARD_HOST} --port ${DASHBOARD_PORT}"]
