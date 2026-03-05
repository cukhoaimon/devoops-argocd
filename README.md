# devoops - DevOps Learning Repo

Helm chart + ArgoCD GitOps setup cho K8s.

## Cấu trúc

```
devops/
├── argocd/
│   └── application.yaml     # ArgoCD Application manifest
└── workload/                # Helm chart
    ├── Chart.yaml
    ├── values.yaml          # Config chính (image, postgresql, autoscaling...)
    └── templates/
        ├── deployment.yaml
        ├── service.yaml
        ├── postgresql.yaml  # PostgreSQL StatefulSet + Service + Secret + PVC
        ├── ingress.yaml
        ├── hpa.yaml
        └── ...
```

## Quick Start

### 1. Cài ArgoCD lên cluster

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Lấy admin password
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d

# Port-forward UI
kubectl port-forward svc/argocd-server -n argocd 8080:443
```

### 2. Cấu hình repo URL

Sửa `argocd/application.yaml`, thay `repoURL` thành URL GitHub repo của bạn:

```yaml
source:
  repoURL: https://github.com/<your-username>/devoops.git
```

Nếu repo private, thêm credentials qua ArgoCD UI: Settings → Repositories.

### 3. Deploy ArgoCD Application

```bash
kubectl apply -f argocd/application.yaml
```

ArgoCD sẽ tự động sync Helm chart lên cluster.

### 4. Deploy thủ công bằng Helm (không cần ArgoCD)

```bash
# Install
helm install workload ./workload

# Upgrade
helm upgrade workload ./workload

# Với custom values
helm upgrade workload ./workload --set postgresql.auth.password=mysecretpassword
```

## PostgreSQL

Mặc định PostgreSQL được bật (`postgresql.enabled: true`) với:

| Config | Giá trị mặc định |
|--------|-----------------|
| Image | `postgres:16-alpine` |
| Database | `appdb` |
| Username | `appuser` |
| Password | `changeme` ⚠️ |
| Storage | `1Gi` |
| Port | `5432` |

App kết nối PostgreSQL qua hostname:

```
<release-name>-workload-postgresql:5432
```

> ⚠️ **Đổi password** trước khi dùng trên production bằng cách override values:
> ```bash
> helm upgrade workload ./workload --set postgresql.auth.password=<strong-password>
> ```
