FROM python:3.12-slim

LABEL maintainer="Security Team"
LABEL description="Google ADK Security Agent via Vertex AI"

RUN apt-get update && apt-get install -y git curl wget ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Go 1.24
RUN wget -q https://go.dev/dl/go1.24.0.linux-amd64.tar.gz \
    && tar -C /usr/local -xzf go1.24.0.linux-amd64.tar.gz \
    && rm go1.24.0.linux-amd64.tar.gz

ENV PATH="/usr/local/go/bin:${PATH}"
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /app/cloned_repos /app/reports /app/forks /app/gcloud

ENTRYPOINT ["python", "adk_security_agent.py"]
