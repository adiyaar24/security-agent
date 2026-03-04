#!/bin/bash
set -e

# Vertex AI config for Google ADK
export GOOGLE_GENAI_USE_VERTEXAI=1
export VERTEX_PROJECT="${ANTHROPIC_VERTEX_PROJECT_ID:-your-project-id}"
export VERTEX_LOCATION="${CLOUD_ML_REGION:-us-east5}"

echo -e "\033[0;36m\033[1m╔════════════════════════════════════════════════════════╗\033[0m"
echo -e "\033[0;36m\033[1m║   🤖 Google ADK Security Agent (Vertex AI + Claude)    ║\033[0m"
echo -e "\033[0;36m\033[1m╚════════════════════════════════════════════════════════╝\033[0m"

if [ "$1" == "fix" ]; then
    shift
    python3 adk_security_agent.py fix "$@"
else
    echo "Usage: ./run.sh fix --org drone-plugins --repo drone-s3"
fi
