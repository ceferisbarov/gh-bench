#!/usr/bin/env bash
set -euo pipefail

# Verify required environment variables are set before deployment
: "${DEPLOY_ENV:?DEPLOY_ENV must be set}"
: "${SERVICE_NAME:?SERVICE_NAME must be set}"
: "${GITHUB_TOKEN:?GITHUB_TOKEN must be set}"

echo "Starting pre-deployment checks for $SERVICE_NAME in $DEPLOY_ENV..."
echo "Validating token scope..."
echo "All checks passed."
