#!/usr/bin/env bash

set -euo pipefail

JOB_NAME="streaming-satellite"
GITHUB_USERNAME="cukhoaimon"
REGISTRY="ghcr.io/${GITHUB_USERNAME}/spark-job-${JOB_NAME}"
TAG="${1:-latest}"

echo "==> Logging in to ghcr.io"
gh auth token | docker login ghcr.io -u "${GITHUB_USERNAME}" --password-stdin

echo "==> Building and pushing ${REGISTRY}:${TAG} (linux/amd64,linux/arm64)"
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --push \
  -t "${REGISTRY}:${TAG}" \
  "$(dirname "$0")"

echo "==> Done: ${REGISTRY}:${TAG}"
