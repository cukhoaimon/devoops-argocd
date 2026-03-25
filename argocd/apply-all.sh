#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

for f in "$SCRIPT_DIR"/*.yaml; do
  echo "Applying $f..."
  kubectl apply -f "$f"
done
