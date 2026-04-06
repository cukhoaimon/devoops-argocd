#!/usr/bin/env bash

set -euo pipefail

JOB_NAME="streaming-satellite"
GITHUB_USERNAME="cukhoaimon"
REGISTRY="ghcr.io/${GITHUB_USERNAME}/spark-job-${JOB_NAME}"
TAG="${1:-latest}"

echo "==> Building ${REGISTRY}:${TAG} (linux/amd64)"

docker build \
  --platform linux/amd64 \
  -t "${REGISTRY}:${TAG}" \
  "$(dirname "$0")"

echo "==> Logging in to ghcr.io"
gh auth token | docker login ghcr.io -u "${GITHUB_USERNAME}" --password-stdin

echo "==> Pushing ${REGISTRY}:${TAG}"
docker push "${REGISTRY}:${TAG}"
echo "==> Done: ${REGISTRY}:${TAG}"
