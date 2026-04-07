#!/usr/bin/env bash
set -euo pipefail

GITHUB_USERNAME="cukhoaimon"
IMAGE_NAME="spark-iceberg"
REGISTRY="ghcr.io/${GITHUB_USERNAME}/${IMAGE_NAME}"

# Tag mặc định là "latest", có thể override: ./build-and-push.sh 3.5.3
TAG="${1:-latest}"

echo "==> Logging in to ghcr.io"
gh auth token | docker login ghcr.io -u "${GITHUB_USERNAME}" --password-stdin

echo "==> Building and pushing ${REGISTRY}:${TAG} (linux/amd64,linux/arm64)"
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --push \
  -t "${REGISTRY}:${TAG}" \
  "$(dirname "$0")"

# Nếu tag cụ thể, cũng push thêm tag latest
if [ "${TAG}" != "latest" ]; then
  docker buildx build \
    --platform linux/amd64,linux/arm64 \
    --push \
    -t "${REGISTRY}:latest" \
    "$(dirname "$0")"
fi

echo "==> Done! Image available at: ${REGISTRY}:${TAG}"
