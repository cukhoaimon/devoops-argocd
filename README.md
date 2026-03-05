# devoops - DevOps Learning Repo

## Overview

This repository is built for **GitOps** using **ArgoCD** to manage infrastructure deployments. It is currently focused on providing a **production-ready PostgreSQL** deployment across multiple environments (`dev`, `uat`, `prod`).

## Architecture

We use **ApplicationSets** inside the `bootstrap` folder to dynamically target environments.

### Project Structure
```
devoops-argocd/
├── bootstrap/
│   └── infrastructure.yaml             # ArgoCD ApplicationSet to deploy PostgreSQL
├── non-prod/
│   └── infrastructure/
│       └── postgresql/
│           ├── Chart.yaml              # Bitnami PostgreSQL Helm Chart Reference
│           ├── values-dev.yaml         # Standalone PostgreSQL (1 CPU / 512Mi / 2Gi)
│           └── values-uat.yaml         # Standalone PostgreSQL (500m / 1Gi / 5Gi)
└── prod/
    └── infrastructure/
        └── postgresql/
            ├── Chart.yaml              # Bitnami PostgreSQL Helm Chart Reference
            └── values-prod.yaml        # HA PostgreSQL with 1 Read Replica (2 CPU / 4Gi / 20Gi)
```

## Quick Start

### 1. Install ArgoCD
If not already installed on your cluster:
```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Lấy admin password
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d

# Port-forward UI
kubectl port-forward svc/argocd-server -n argocd 8080:443
```

### 2. Configure Credentials (CRITICAL)
Before deploying, you **must** create the PostgreSQL password secrets in the target namespaces (`dev`, `uat`, `prod`). The Helm charts are tightly coupled to an `existingSecret` for security.

```bash
# Example for 'dev' environment
kubectl create namespace dev
kubectl create secret generic postgresql-credentials \
  --namespace dev \
  --from-literal=postgres-password="SuperSecretAdminPassword" \
  --from-literal=password="SuperSecretAppPassword"
```
*(Repeat for `uat` and `prod` namespaces with environment-appropriate passwords)*

### 3. Deploy the Infrastructure

We use ArgoCD's `ApplicationSet` generator to automatically spin up PostgreSQL in the appropriate namespaces based on the directories.

```bash
kubectl apply -f bootstrap/infrastructure.yaml
```

ArgoCD will automatically create three Applications:
- `dev-postgresql` (deployed to `dev` namespace)
- `uat-postgresql` (deployed to `uat` namespace)
- `prod-postgresql` (deployed to `prod` namespace)

## PostgreSQL Details

The databases are initialized with the following connection details (passwords are pulled from the secrets above):

- **Database:** `appdb`
- **Username:** `appuser`
- **Port:** `5432`

### Connecting from inside the cluster
```bash
# In Dev
psql -h dev-postgresql-primary.dev.svc.cluster.local -U appuser -d appdb

# In Prod (Primary Node)
psql -h prod-postgresql-primary.prod.svc.cluster.local -U appuser -d appdb

# In Prod (Read Replica)
psql -h prod-postgresql-read.prod.svc.cluster.local -U appuser -d appdb
```
