# Weekly Learning Summary — 2026-03-17 to 2026-03-24

## Overview

| Date | Topic |
|------|-------|
| 2026-03-17 | Deploy simple web app — Helm + ArgoCD GitOps |
| 2026-03-18 | Deploy HBase on Kubernetes — StatefulSet + ZooKeeper |
| 2026-03-19 | Fix HBase — ConfigMap, ZooKeeper dependency, Helm helpers |
| 2026-03-22 | Deploy MinIO via AiStor Operator + Sealed Secrets |
| 2026-03-24 | Deploy Iceberg REST Catalog — integrate với MinIO |

---

## Milestone 1 — GitOps cơ bản với Helm + ArgoCD (2026-03-17)

- Build Docker image (nginx) serve static HTML
- Viết Helm chart với Deployment, Service, Ingress
- ArgoCD auto-sync từ Git remote repo → minikube

**Key lessons:**
- `pullPolicy: Never` + `eval $(minikube docker-env)` để dùng local image
- ArgoCD chỉ sync được từ **remote Git repo**, không phải local filesystem
- Ingress backend phải là **Service**, không phải Pod trực tiếp

---

## Milestone 2 — HBase trên Kubernetes (2026-03-18 → 2026-03-20)

### Architecture
```
ArgoCD → Helm chart (hbase/)
           ├── ZooKeeper StatefulSet  (zookeeper:3.9)
           ├── HBase Master StatefulSet (harisekhon/hbase:2.1)
           ├── HBase RegionServer StatefulSet
           ├── ConfigMap (hbase-site.xml)
           └── Services (headless + ClusterIP)
```

### hbase-site.xml config quan trọng
```xml
<property>
  <name>hbase.zookeeper.quorum</name>
  <value>{{ .Release.Name }}-zookeeper:2181</value>  <!-- DNS nội bộ K8s -->
</property>
<property>
  <name>hbase.cluster.distributed</name>
  <value>true</value>
</property>
<property>
  <name>hbase.unsafe.stream.capability.enforce</name>
  <value>false</value>   <!-- cần khi rootdir là local filesystem -->
</property>
```

### Helm `_helpers.tpl`
- Dùng để tạo reusable labels/names thay vì hardcode ở từng template
- Pattern: `{{ include "chart-name.fullname" . }}`

**Key lessons:**
- HBase distributed mode **bắt buộc** có ZooKeeper — dù chỉ 1 node
- ZooKeeper headless service dùng DNS `<release>-zookeeper:2181`
- `hbase.master.hostname` phải match tên Service để RegionServer tìm được Master
- StatefulSet dùng `volumeClaimTemplates` để cấp PVC riêng cho từng pod
- Phân biệt headless Service (`clusterIP: None`) vs ClusterIP Service:
  - Headless → DNS `pod-0.svc-name` → dùng cho StatefulSet
  - ClusterIP → load-balance traffic → dùng cho client access

---

## Milestone 3 — MinIO via AiStor Operator + Sealed Secrets (2026-03-22 → 2026-03-23)

### Architecture
```
ArgoCD → Helm chart (minio/aistor-operator)
           ├── ObjectStore CR  → Operator tạo MinIO deployment
           ├── SealedSecret    → Operator/Controller decrypt → Secret
           └── values.yaml     → pool config, NodePort, resource limits
```

### ObjectStore CR config
```yaml
pools:
  - servers: 1
    volumesPerServer: 1
    size: 10Gi
services:
  minio:
    serviceType: NodePort
    nodePort: 31000       # S3 API
    consoleNodePort: 31001 # Web UI
```

### Sealed Secrets
- **Vấn đề:** Không thể commit plain-text credentials lên Git
- **Giải pháp:** Bitnami Sealed Secrets — encrypt bằng public key của cluster controller
- `kubeseal` CLI → `SealedSecret` manifest (safe to commit) → Controller decrypt → `Secret`
- Encrypted value chỉ decrypt được trên **đúng cluster** đó

**Key lessons:**
- Operator pattern: deploy một CRD + controller, rồi tạo custom resource thay vì viết Deployment/Service tay
- `SealedSecret` chỉ có thể decrypt bởi controller trong cluster — an toàn để push lên public Git
- Cần backup master key của Sealed Secrets controller nếu không sẽ mất khả năng decrypt

---

## Milestone 4 — Iceberg REST Catalog (2026-03-24)

### Architecture
```
ArgoCD → Helm chart (iceberg/)
           ├── Deployment (tabulario/iceberg-rest:0.10.0)
           ├── Service (ClusterIP port 8181)
           └── PVC (SQLite database backend)

Iceberg REST ──► MinIO (S3 API) ──► lưu data files
              ──► SQLite PVC      ──► lưu catalog metadata
```

### Env config quan trọng
```yaml
CATALOG_WAREHOUSE: s3://warehouse/
CATALOG_IO__IMPL: org.apache.iceberg.aws.s3.S3FileIO
CATALOG_S3_ENDPOINT: http://minio.minio.svc.cluster.local:9000
CATALOG_S3_PATH__STYLE__ACCESS: "true"  # MinIO dùng path-style, không phải virtual-hosted
AWS_REGION: us-east-1  # bắt buộc dù MinIO không dùng region
```

### Docker Compose local testing
- Dùng `docker-compose.yaml` để test locally trước khi deploy lên K8s
- Stack: `minio` + `mc` (init bucket) + `rest` (iceberg catalog) + `spark-iceberg`
- `mc` container dùng `entrypoint` script để init bucket + set policy

**Key lessons:**
- Iceberg REST Catalog tách biệt **metadata** (catalog) khỏi **data storage** (S3/MinIO)
- MinIO cần `path-style access` (`s3://host/bucket/key`) thay vì virtual-hosted (`s3://bucket.host/key`)
- `AWS_REGION` phải set dù dùng MinIO vì AWS SDK require field này
- Credentials inject qua `secretKeyRef` từ SealedSecret đã tạo ở Milestone 3
- Service DNS trong K8s: `<svc-name>.<namespace>.svc.cluster.local:<port>`

---

## Tổng kết kiến trúc Data Stack

```
Git Push
  └── ArgoCD detects
        ├── hbase/         → namespace: non-prod
        │     ├── ZooKeeper
        │     ├── HBase Master
        │     └── HBase RegionServer
        ├── minio/         → namespace: data-warehouse
        │     └── MinIO ObjectStore (via AiStor Operator)
        └── iceberg/       → namespace: data-warehouse
              └── Iceberg REST Catalog → MinIO (S3) + SQLite
```

---

## Key Concepts Recap

| Concept | Khi nào dùng |
|---------|--------------|
| StatefulSet | Workload cần stable identity, persistent storage (DB, ZooKeeper, HBase) |
| Headless Service | Để StatefulSet pods có DNS riêng `pod-0.svc` |
| Operator pattern | Quản lý complex stateful apps (MinIO, Kafka, Postgres) |
| Sealed Secrets | Commit encrypted credentials an toàn lên Git |
| Helm `_helpers.tpl` | Reusable template functions, tránh hardcode |
| ArgoCD `syncPolicy.automated` | prune=true xóa resource bị remove, selfHeal=true tự fix drift |
| `CreateNamespace=true` | syncOptions để ArgoCD tự tạo namespace nếu chưa có |
