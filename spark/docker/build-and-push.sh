#!/usr/bin/env bash
set -euo pipefail

GITHUB_USERNAME="cukhoaimon"
IMAGE_NAME="spark-iceberg"
REGISTRY="ghcr.io/${GITHUB_USERNAME}/${IMAGE_NAME}"

# Tag mặc định là "latest", có thể override: ./build-and-push.sh 3.5.3
TAG="${1:-latest}"

echo "==> Building ${REGISTRY}:${TAG}"
docker build \
  --platform linux/amd64 \
  -t "${REGISTRY}:${TAG}" \
  "$(dirname "$0")"

echo "==> Logging in to ghcr.io"
gh auth token | docker login ghcr.io -u "${GITHUB_USERNAME}" --password-stdin

echo "==> Pushing ${REGISTRY}:${TAG}"
docker push "${REGISTRY}:${TAG}"

# Nếu tag cụ thể, cũng push thêm tag latest
if [ "${TAG}" != "latest" ]; then
  docker tag "${REGISTRY}:${TAG}" "${REGISTRY}:latest"
  echo "==> Pushing ${REGISTRY}:latest"
  docker push "${REGISTRY}:latest"
fi

echo "==> Done! Image available at: ${REGISTRY}:${TAG}"
