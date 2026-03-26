#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Fixing argocd-repo-server (clearing stuck EmptyDir)..."
REPO_SERVER_POD=$(kubectl get pod -n argocd -l app.kubernetes.io/name=argocd-repo-server -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
if [ -n "$REPO_SERVER_POD" ]; then
  kubectl delete pod "$REPO_SERVER_POD" -n argocd
  echo "    Deleted $REPO_SERVER_POD, waiting for it to be ready..."
  kubectl rollout status deployment/argocd-repo-server -n argocd --timeout=120s
else
  echo "    argocd-repo-server pod not found, skipping."
fi

echo ""
echo "==> Applying all ArgoCD Applications..."
for f in "$SCRIPT_DIR/argocd"/*.yaml; do
  echo "    Applying $f..."
  kubectl apply -f "$f"
done

echo ""
echo "==> Waiting for ArgoCD apps to sync..."
sleep 5
kubectl get applications -n argocd

echo ""
echo "==> Done. Monitor Spark pods with:"
echo "    kubectl get pods -n spark -w"
