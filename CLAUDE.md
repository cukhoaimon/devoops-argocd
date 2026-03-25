# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Is

A **DevOps learning repo** using GitOps with **ArgoCD** on **minikube**. Changes pushed to the `main` branch of the remote GitHub repo (`cukhoaimon/devoops-argocd`) are automatically synced to the local minikube cluster via ArgoCD.

## Key Commands

```bash
# Bootstrap ArgoCD (first-time only)
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl port-forward svc/argocd-server -n argocd 8080:443

# Apply an ArgoCD Application (first-time only — after this, GitOps takes over)
kubectl apply -f argocd/application.yaml
kubectl apply -f argocd/hbase-application.yaml
kubectl apply -f argocd/minio-application.yaml
kubectl apply -f argocd/iceberg-application.yaml
kubectl apply -f argocd/spark-application.yaml

# Build the nginx web image into minikube's Docker daemon
eval $(minikube docker-env)
docker build -t my-web-app:v1 .

# Build & push the custom Spark image to ghcr.io
./spark/docker/build-and-push.sh [optional-tag]

# Local Iceberg + MinIO + Spark testing (Docker Compose)
docker compose up

# Helm chart dry-run / template preview
helm template <release-name> ./<chart-dir>
helm install <release-name> ./<chart-dir> --dry-run

# Add local DNS for ingress
echo "$(minikube ip) my-web.local" | sudo tee -a /etc/hosts
```

## Architecture Overview

All components are deployed via **ArgoCD** pointing at `github.com/cukhoaimon/devoops-argocd` (main branch). Each subdirectory is its own Helm chart with a corresponding ArgoCD `Application` manifest under `argocd/`.

```
argocd/               # ArgoCD Application manifests (one per component)
my-web/               # Helm chart — nginx static site (Deployment + Service + Ingress)
hbase/                # Helm chart — HBase (ZooKeeper + Master + RegionServer StatefulSets)
minio/aistor-operator/# Helm chart — MinIO via AiStor Operator + SealedSecret credentials
iceberg/              # Helm chart — Iceberg REST Catalog (REST server + SQLite PVC)
spark/                # Helm chart — Spark on K8s + custom image (spark/docker/)
docker-compose.yaml   # Local test stack: MinIO + Iceberg REST + Spark
Dockerfile            # nginx:alpine serving index.html for my-web
docs/                 # Weekly learning notes per milestone
```

### Namespace Assignments
| Component | Namespace |
|-----------|-----------|
| my-web | default |
| hbase | non-prod |
| minio | data-warehouse |
| iceberg | data-warehouse |
| spark | spark |

### Data Stack Integration
```
Iceberg REST Catalog ──► MinIO (S3 API, NodePort 31000) — stores data files
                    ──► SQLite PVC                      — stores catalog metadata
Spark ──► Iceberg REST ──► MinIO
```

## Important Patterns

- **Local images on minikube**: use `eval $(minikube docker-env)` before `docker build`, and set `pullPolicy: Never` in values.
- **ArgoCD requires remote Git**: it cannot sync from local filesystem — push to GitHub first.
- **Sealed Secrets**: credentials are encrypted with `kubeseal` and committed as `SealedSecret` manifests. They can only be decrypted by the controller in the original cluster. Back up the controller's master key.
- **MinIO path-style access**: set `CATALOG_S3_PATH__STYLE__ACCESS: "true"` — MinIO uses path-style, not virtual-hosted.
- **`AWS_REGION`**: must be set even when using MinIO (AWS SDK requires it).
- **HBase ZooKeeper DNS**: use `<release-name>-zookeeper:2181` as the quorum address inside the cluster.
- **`CreateNamespace=true`** in `syncOptions` lets ArgoCD auto-create namespaces.
