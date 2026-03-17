# Milestone 1 — Local Kubernetes with Helm & ArgoCD

## What was accomplished

- Installed and configured **Kubernetes** (minikube), **Helm**, and **ArgoCD** locally
- Built a Docker image (nginx) serving a static `index.html`
- Wrote a **Helm chart** (`my-web`) with Deployment, Service, and Ingress templates
- Configured **ArgoCD** to watch the Git repository and auto-sync on every push
- Exposed the app locally via **Ingress** at `http://my-web.local`

## Architecture

```
Git Push → ArgoCD detects change → syncs to minikube

Ingress (my-web.local)
    └── Service (ClusterIP)
            └── Deployment
                    └── Pod (nginx:alpine serving index.html)
```

## ArgoCD Sync Result

App health: **Healthy** | Sync status: **Synced** to `main`

![ArgoCD Application Detail Tree](./Screenshot%202026-03-17%20at%2023.29.17.png)

## Key commands

```bash
# Build image into minikube
eval $(minikube docker-env)
docker build -t my-web-app:v1 .

# Deploy via Helm, this step can skip when GitOps configured
helm install my-release ./my-web

# Apply ArgoCD application, only run for the first time
kubectl apply -f argocd/application.yaml

# Add local DNS entry
echo "$(minikube ip) my-web.local" | sudo tee -a /etc/hosts
```

## Lessons learned

- `apiVersion` in `Chart.yaml` (`v2`) is Helm-specific — Kubernetes manifests use `apps/v1`, `v1`, `networking.k8s.io/v1`, etc.
- ArgoCD requires the chart to be in a **Git remote** repo, not local filesystem
- Ingress needs a **Service** as backend — it cannot route directly to pods
- `pullPolicy: Never` + `eval $(minikube docker-env)` is required for locally built images, or build and using helm to load image.
