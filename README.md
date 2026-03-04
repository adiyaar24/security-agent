# Google ADK Security Agent (Vertex AI & Claude Integration)

This repository contains an autonomous security agent completely re-architected to use the [Google Agent Development Kit (ADK)](https://google.github.io/adk-docs/). It leverages **Vertex AI Model Garden** and **LiteLLM** to power the logic using Claude 4.5 directly on GCP infrastructure.


## Installation

1. **Prerequisites**
   - Python 3.10+
   - [Google Cloud SDK (gcloud)](https://cloud.google.com/sdk/docs/install)
   - Docker & Docker Compose (optional)

2. **Authenticate with Google Cloud**
   ```bash
   gcloud auth application-default login
   gcloud config set project YOUR_VERTEX_PROJECT_ID
