# Daily Learning Summary — 2026-03-25

## Change from Yesterday (2026-03-24) to Today (2026-03-25)

Yesterday, I finished the first Spark integration and temporarily downscaled ZooKeeper while stabilizing the cluster.
Today, I moved from "Spark-only setup" to a more complete Spark + Iceberg + MinIO + Jupyter workflow with ArgoCD.

## What I Changed Today

### 1) Added Jupyter as a GitOps-managed app
- Created a new Helm chart under `jupyter/` (Deployment, Service, Ingress, PVC, Values)
- Added `argocd/jupyter-application.yaml` so ArgoCD can sync Jupyter automatically into namespace `spark`
- Wired Jupyter to Spark Connect using:
  - `SPARK_CONNECT_URL=sc://spark-connect-server.spark.svc.cluster.local:15002`

### 2) Stabilized Spark image/runtime behavior
- Kept Spark Connect on custom image `ghcr.io/cukhoaimon/spark-iceberg:latest`
- Set image pull policy to `Always` to ensure latest image is used after pushes
- Updated Dockerfile permissions (`chmod 644`) for downloaded JARs so non-root runtime user can read them

### 3) Fixed Iceberg + MinIO endpoint/DNS consistency
- Updated endpoints from old MinIO DNS to:
  - `primary-object-store.data-warehouse.svc.cluster.local:9000`
- Applied this consistently in:
  - `iceberg/templates/deployment-sqlite.yaml`
  - `spark/templates/configmap.yaml`

### 4) Improved AWS/MinIO compatibility for Spark executors
- Added missing region config in Spark defaults (`us-east-1`) for both driver and executor
- Added extra Java options for AWS region resolution
- Reinforced path-style S3 settings for MinIO

### 5) Strengthened credentials handling in Spark namespace
- Replaced plain Kubernetes `Secret` with `SealedSecret` for `minio-credentials`
- This keeps GitOps workflow secure while allowing in-cluster decryption

### 6) Networking and ingress alignment
- Added explicit `ingressClassName: traefik` for `my-web` ingress
- Reduced `my-web` replicas from 3 to 1 for local-resource-friendly setup
- Added helper script `argocd/apply-all.sh` to bootstrap all ArgoCD applications quickly

## Key Things I Learned Today

1. Spark + Iceberg often fails for non-obvious reasons when endpoint DNS is inconsistent across components; every catalog and S3 endpoint must match exactly.
2. Even with MinIO, region settings are still required in many Spark/AWS SDK code paths (driver + executor).
3. Pre-baked Spark images are more reliable than runtime package download for Spark Connect + Iceberg dependencies.
4. `SealedSecret` is the right GitOps default for credentials; plain Secret in repo is risky.
5. Running Jupyter through Spark Connect gives a cleaner architecture than bundling notebook concerns directly into the Spark service.

## Net Progress vs Yesterday

- Yesterday: Spark was introduced.
- Today: Spark stack became usable end-to-end with Jupyter client access, corrected Iceberg/MinIO connectivity, stronger secret management, and cleaner ArgoCD bootstrap flow.
