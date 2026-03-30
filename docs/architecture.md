# Architecture Overview

A GitOps-driven local Kubernetes data platform on OrbStack. Changes pushed to GitHub are automatically synced to the cluster via ArgoCD.

---

## C4 Level 1 — System Context

```mermaid
C4Context
  title System Context — DevOps Learning Platform

  Person(user, "Data Engineer", "Writes notebooks, submits Spark jobs, explores data")
  Person(admin, "Platform Admin", "Manages GitOps config, credentials, cluster setup")

  System(platform, "Local Data Platform", "Kubernetes cluster on OrbStack running a full data stack: Jupyter, Spark, Iceberg, MinIO, Kafka, HBase")
  System_Ext(github, "GitHub (cukhoaimon/devoops-argocd)", "Source of truth for all Kubernetes manifests")
  System_Ext(ghcr, "GitHub Container Registry (ghcr.io)", "Hosts custom Spark Docker image")
  System_Ext(orbstack, "OrbStack", "Local VM host sharing Docker daemon with macOS")

  Rel(user, platform, "Accesses JupyterLab via browser", "HTTP jupyter.local")
  Rel(admin, github, "Pushes Helm chart changes", "git push")
  Rel(github, platform, "GitOps sync via ArgoCD", "HTTPS polling / webhook")
  Rel(platform, ghcr, "Pulls custom Spark image", "HTTPS")
  Rel(admin, ghcr, "Pushes custom Spark image", "docker push")
  Rel(orbstack, platform, "Hosts the Kubernetes cluster", "")
```

---

## C4 Level 2 — Containers

```mermaid
C4Container
  title Container Diagram — Kubernetes Workloads

  Person(user, "Data Engineer")

  Boundary(argocd_ns, "Namespace: argocd") {
    Container(argocd, "ArgoCD", "Kubernetes Operator", "Watches GitHub repo, applies Helm charts to cluster on every push to main")
  }

  Boundary(spark_ns, "Namespace: spark") {
    Container(jupyter, "JupyterLab", "quay.io/jupyter/pyspark-notebook", "Interactive notebook environment, connects to Spark Connect over gRPC")
    Container(spark_connect, "Spark Connect Server", "ghcr.io/cukhoaimon/spark-iceberg:3.5.3", "Accepts remote Spark sessions via gRPC port 15002, runs driver + spawns executor pods")
    Container(spark_executor, "Spark Executor Pods", "ghcr.io/cukhoaimon/spark-iceberg:3.5.3", "Dynamically created by Spark driver, run actual computation tasks")
  }

  Boundary(dw_ns, "Namespace: data-warehouse") {
    Container(iceberg, "Iceberg REST Catalog", "tabulario/iceberg-rest:0.10.0", "Manages table metadata, exposes REST API on port 8181, uses SQLite for persistence")
    Container(minio, "MinIO Object Store", "quay.io/minio/minio:latest", "S3-compatible object storage, stores Iceberg data files. NodePort 31000 for external S3 API access")
    ContainerDb(sqlite, "SQLite DB", "File on PVC", "Stores Iceberg catalog metadata (table schemas, snapshots, manifests)")
    ContainerDb(minio_storage, "MinIO PVC", "10Gi PersistentVolume", "Persistent storage for all data files (Parquet, Avro, ORC)")
  }

  Boundary(kafka_ns, "Namespace: kafka") {
    Container(kafka, "Kafka Cluster", "Strimzi / Kafka 4.2.0", "Event streaming. 1 controller + 1 broker, KRaft mode (no ZooKeeper)")
  }

  Boundary(nonprod_ns, "Namespace: non-prod") {
    Container(hbase, "HBase", "harisekhon/hbase:2.1", "Distributed wide-column store. Currently downscaled to 0 replicas")
    Container(zookeeper, "ZooKeeper", "zookeeper:3.9", "Coordination service for HBase. Currently downscaled to 0 replicas")
  }

  Boundary(default_ns, "Namespace: default") {
    Container(web, "my-web", "nginx:alpine", "Static website served via Traefik Ingress at my-web.local")
  }

  Rel(user, jupyter, "Opens notebook", "HTTP :80 → jupyter.local (Traefik Ingress)")
  Rel(jupyter, spark_connect, "Submits Spark session", "gRPC sc:// port 15002")
  Rel(spark_connect, spark_executor, "Spawns executor pods", "Kubernetes API")
  Rel(spark_connect, iceberg, "Reads/writes table metadata", "HTTP port 8181")
  Rel(spark_connect, minio, "Reads/writes data files", "S3 API port 9000")
  Rel(spark_executor, minio, "Reads/writes data files", "S3 API port 9000")
  Rel(iceberg, minio, "Stores/fetches data files", "S3 API port 9000")
  Rel(iceberg, sqlite, "Persists catalog metadata", "JDBC jdbc:sqlite://")
  Rel(minio, minio_storage, "Persists object data", "")
  Rel(argocd, spark_connect, "Deploys & reconciles", "Kubernetes API")
  Rel(argocd, iceberg, "Deploys & reconciles", "Kubernetes API")
  Rel(argocd, minio, "Deploys & reconciles", "Kubernetes API")
  Rel(argocd, kafka, "Deploys & reconciles", "Kubernetes API")
```

---

## C4 Level 3 — Spark Component Detail

```mermaid
C4Component
  title Component Diagram — Spark Namespace

  Boundary(spark_deploy, "Spark Connect Deployment") {
    Component(connect_server, "Spark Connect gRPC Server", "start-connect-server.sh", "Listens on port 15002, manages Spark sessions for remote clients")
    Component(spark_driver, "Spark Driver", "JVM process", "Coordinates job execution, communicates with K8s API to launch executor pods")
    Component(spark_ui, "Spark Web UI", "Jetty HTTP server", "Job monitoring UI on port 4040")
    Component(block_mgr, "Block Manager", "Netty server", "Shuffle data transfer between driver and executors, port 7078")
  }

  Boundary(spark_config, "Configuration") {
    Component(defaults_conf, "spark-defaults.conf", "ConfigMap volume mount", "Iceberg catalog config, MinIO S3 endpoints, executor resources, K8s cluster config")
    Component(minio_secret, "minio-credentials", "SealedSecret → Secret", "AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY for S3 access")
    Component(ivy_cache, "Ivy Cache PVC", "2Gi PersistentVolume", "Caches downloaded JARs to speed up repeated job submissions")
  }

  Boundary(spark_rbac, "RBAC") {
    Component(sa, "spark-driver ServiceAccount", "K8s ServiceAccount", "Identity used by Spark driver pod")
    Component(role, "spark-driver-role", "K8s Role", "Grants: pods CRUD, services CRUD, configmaps CRUD, pod logs read")
    Component(rb, "RoleBinding", "K8s RoleBinding", "Binds spark-driver-role to spark-driver ServiceAccount")
  }

  Boundary(spark_svc, "Services") {
    Component(svc_connect, "spark-connect-server Service", "ClusterIP", "Exposes port 15002 (gRPC), 4040 (UI), 8888 (reserved)")
    Component(svc_headless, "spark-driver-headless Service", "Headless ClusterIP", "Enables executor-to-driver communication on ports 7078, 2222")
  }

  Rel(connect_server, spark_driver, "Delegates job execution to")
  Rel(spark_driver, sa, "Runs as")
  Rel(sa, role, "Bound via RoleBinding")
  Rel(spark_driver, defaults_conf, "Reads Iceberg/S3 config from")
  Rel(spark_driver, minio_secret, "Reads S3 credentials from")
  Rel(spark_driver, ivy_cache, "Caches JARs in")
  Rel(svc_connect, connect_server, "Routes traffic to")
  Rel(svc_headless, spark_driver, "Routes executor callbacks to")
```

---

## GitOps Flow

```mermaid
flowchart TD
  subgraph dev["Developer Workstation (macOS + OrbStack)"]
    A[Edit Helm chart\nor values.yaml]
    B[git commit + push\nto main branch]
    D[docker build\ncustom Spark image]
    E[build-and-push.sh\ngh auth token login]
  end

  subgraph github["GitHub"]
    C[(cukhoaimon/devoops-argocd\nmain branch)]
    F[(ghcr.io/cukhoaimon/\nspark-iceberg:3.5.3)]
  end

  subgraph cluster["OrbStack Kubernetes Cluster"]
    direction TB
    G[ArgoCD\npolls every 3 min\nor on webhook]
    H{Diff detected?}
    I[kubectl apply\nHelm template render]
    J[Kubernetes API Server]

    subgraph apps["Applications"]
      K[my-web\nNamespace: default]
      L[HBase\nNamespace: non-prod]
      M[MinIO\nNamespace: data-warehouse]
      N[Iceberg REST\nNamespace: data-warehouse]
      O[Spark Connect\nNamespace: spark]
      P[JupyterLab\nNamespace: spark]
      Q[Kafka\nNamespace: kafka]
    end
  end

  A --> B --> C
  D --> E --> F
  C -->|"HTTPS polling\n(automated sync)"| G
  G --> H
  H -->|"Yes — prune=true\nselfHeal=true"| I
  I --> J --> apps
  O -->|Pull on startup| F

  style dev fill:#e8f4f8
  style github fill:#f0f0f0
  style cluster fill:#e8f8e8
```

---

## Data Flow — Jupyter → Spark → Iceberg → MinIO

```mermaid
sequenceDiagram
  actor User
  participant JL as JupyterLab<br/>(spark ns, jupyter.local)
  participant SC as Spark Connect<br/>(spark ns, :15002)
  participant SD as Spark Driver<br/>(spark ns)
  participant SE as Spark Executors<br/>(spark ns, dynamic pods)
  participant IR as Iceberg REST<br/>(data-warehouse ns, :8181)
  participant SQ as SQLite PVC<br/>(catalog metadata)
  participant MN as MinIO<br/>(data-warehouse ns, :9000)

  User->>JL: Open notebook, run PySpark cell
  JL->>SC: Connect via sc://...spark-connect-server...:15002 (gRPC)
  SC->>SD: Spin up Spark Driver session
  SD->>SE: Launch executor pods via K8s API

  Note over SD,IR: CREATE TABLE or INSERT operation
  SD->>IR: POST /v1/namespaces/{ns}/tables (Iceberg REST API)
  IR->>SQ: Write table metadata (schema, snapshot, manifest list)
  IR-->>SD: Table location: s3://warehouse/db/table/

  SD->>SE: Distribute write tasks
  SE->>MN: PUT s3://warehouse/db/table/data/*.parquet (S3 API)
  MN-->>SE: 200 OK
  SE-->>SD: Task complete
  SD->>IR: POST /v1/.../tables/{table}/snapshots (commit snapshot)
  IR->>SQ: Persist new snapshot pointer

  Note over SD,IR: SELECT / read operation
  SD->>IR: GET /v1/.../tables/{table} (fetch current snapshot)
  IR->>SQ: Read latest snapshot metadata
  IR-->>SD: Manifest list location in MinIO
  SD->>MN: GET s3://warehouse/db/table/metadata/snap-*.avro
  MN-->>SD: Manifest list (list of data files)
  SD->>SE: Distribute read tasks
  SE->>MN: GET s3://warehouse/db/table/data/*.parquet
  MN-->>SE: Parquet file bytes
  SE-->>SD: Results
  SD-->>SC: DataFrame result
  SC-->>JL: Display in notebook
  JL-->>User: Shows query output
```

---

## Network Topology

```mermaid
graph TB
  subgraph macOS["macOS Host (OrbStack)"]
    browser["Browser\njupyter.local\nmy-web.local"]
    s3client["S3 Client\nlocalhost:31000"]
    dockerd["Docker Daemon\n(shared with K8s cluster)"]
  end

  subgraph k8s["Kubernetes Cluster (OrbStack)"]
    subgraph ingress_layer["Ingress Layer"]
      traefik["Traefik Ingress Controller\n127.0.0.1:80"]
    end

    subgraph spark_ns["Namespace: spark"]
      jupyter_svc["jupyter :8888"]
      spark_svc["spark-connect-server :15002, :4040"]
      spark_headless["spark-driver-headless :7078, :2222"]
      executor_pods["executor pods (dynamic)"]
    end

    subgraph dw_ns["Namespace: data-warehouse"]
      iceberg_svc["iceberg-rest-catalog :8181\nClusterIP"]
      minio_svc["primary-object-store :9000\nClusterIP (also NodePort 31000)"]
      minio_console["primary-object-store :9001\nNodePort 31001"]
    end

    subgraph kafka_ns["Namespace: kafka"]
      kafka_plain["my-kafka-cluster :9092 (plain)"]
      kafka_tls["my-kafka-cluster :9093 (TLS)"]
    end

    subgraph nonprod_ns["Namespace: non-prod (downscaled)"]
      zk_svc["zookeeper :2181, :2888, :3888"]
      hbase_master_svc["hbase-master :16000, :16010"]
      hbase_rs_svc["hbase-regionserver :16020, :16030"]
    end

    subgraph default_ns["Namespace: default"]
      web_svc["my-web :80"]
    end

    subgraph argocd_ns["Namespace: argocd"]
      argocd_svc["argocd-server :443"]
    end

    k8s_api["Kubernetes API Server\nhttps://kubernetes.default.svc"]
  end

  subgraph external["External"]
    github_repo["GitHub\ncukhoaimon/devoops-argocd"]
    ghcr_reg["ghcr.io\nSpark image"]
  end

  browser -->|"HTTP :80 Host: jupyter.local"| traefik
  browser -->|"HTTP :80 Host: my-web.local"| traefik
  s3client -->|"NodePort 31000"| minio_svc
  traefik -->|"ClusterIP"| jupyter_svc
  traefik -->|"ClusterIP"| web_svc
  jupyter_svc -->|"gRPC :15002"| spark_svc
  spark_svc -->|"HTTP :8181"| iceberg_svc
  spark_svc -->|"S3 :9000"| minio_svc
  executor_pods -->|"S3 :9000"| minio_svc
  executor_pods -->|"callback :7078"| spark_headless
  iceberg_svc -->|"S3 :9000"| minio_svc
  spark_svc -->|"spawn pods"| k8s_api
  k8s_api -->|"executor pods"| executor_pods
  argocd_svc -->|"HTTPS poll"| github_repo
  argocd_svc -->|"apply"| k8s_api
  spark_svc -->|"pull image"| ghcr_reg
  hbase_master_svc -->|":2181"| zk_svc
  hbase_rs_svc -->|":2181"| zk_svc

  style macOS fill:#dbeafe
  style k8s fill:#dcfce7
  style external fill:#fef9c3
```

---

## Persistent Storage Map

```mermaid
graph LR
  subgraph pvcs["PersistentVolumeClaims"]
    pvc1["hbase-rootdir\n5Gi ReadWriteMany\nns: non-prod"]
    pvc2["hbase-rs-storage\n5Gi per replica\nns: non-prod"]
    pvc3["minio-storage\n10Gi\nns: data-warehouse"]
    pvc4["iceberg-catalog-storage\n1Gi\nns: data-warehouse"]
    pvc5["spark-ivy-cache\n2Gi\nns: spark"]
    pvc6["jupyter-notebooks\n1Gi\nns: spark"]
  end

  hbase_master["HBase Master"] -->|"rootdir shared"| pvc1
  hbase_rs["HBase RegionServer"] -->|"rootdir shared"| pvc1
  hbase_rs -->|"per-replica WAL/store"| pvc2
  minio_pod["MinIO Pod"] --> pvc3
  iceberg_pod["Iceberg REST Pod"] -->|"SQLite DB"| pvc4
  spark_pod["Spark Connect Pod"] -->|"JAR cache"| pvc5
  jupyter_pod["JupyterLab Pod"] -->|"/home/jovyan/work"| pvc6
```

---

## Secrets & Credentials Flow

```mermaid
flowchart LR
  subgraph local["Local (Admin)"]
    raw["Raw credentials\n.env / manual input"]
    kubeseal["kubeseal CLI\n+ cluster public key"]
  end

  subgraph git["Git (GitHub)"]
    sealed["SealedSecret YAML\n(encrypted, safe to commit)"]
  end

  subgraph cluster["Kubernetes Cluster"]
    controller["Sealed Secrets Controller\n(holds master private key)"]
    secret["Kubernetes Secret\n(decrypted at runtime)"]
    minio_pod2["MinIO Pod\nMINIO_ROOT_USER\nMINIO_ROOT_PASSWORD"]
    spark_pod2["Spark Pod\nAWS_ACCESS_KEY_ID\nAWS_SECRET_ACCESS_KEY"]
  end

  raw -->|"kubeseal --cert"| kubeseal
  kubeseal --> sealed
  sealed -->|"ArgoCD apply"| controller
  controller -->|"decrypt + create"| secret
  secret -->|"envFrom secretRef"| minio_pod2
  secret -->|"envFrom secretRef"| spark_pod2

  style local fill:#fef3c7
  style git fill:#f0f0f0
  style cluster fill:#dcfce7
```

---

## Component Summary Table

| Component | Image | Namespace | Replicas | Ports | Storage | Access |
|-----------|-------|-----------|----------|-------|---------|--------|
| **ArgoCD** | argoproj/argocd | argocd | 1 | 443 | — | kubectl port-forward :8080 |
| **my-web** | nginx:alpine | default | 1 | 80 | — | `my-web.local` (Ingress) |
| **ZooKeeper** | zookeeper:3.9 | non-prod | **0** (down) | 2181/2888/3888 | emptyDir | Internal only |
| **HBase Master** | harisekhon/hbase:2.1 | non-prod | **0** (down) | 16000/16010 | Shared 5Gi PVC | Internal only |
| **HBase RegionServer** | harisekhon/hbase:2.1 | non-prod | **0** (down) | 16020/16030 | 5Gi per replica | Internal only |
| **MinIO** | quay.io/minio/minio | data-warehouse | 1 | 9000/9001 | 10Gi PVC | NodePort 31000/31001 |
| **Iceberg REST** | tabulario/iceberg-rest:0.10.0 | data-warehouse | 1 | 8181 | 1Gi PVC (SQLite) | ClusterIP only |
| **Spark Connect** | ghcr.io/cukhoaimon/spark-iceberg:3.5.3 | spark | 1 | 15002/4040/7078 | 2Gi Ivy cache | ClusterIP only |
| **Spark Executors** | ghcr.io/cukhoaimon/spark-iceberg:3.5.3 | spark | 2 (dynamic) | — | — | Internal only |
| **JupyterLab** | quay.io/jupyter/pyspark-notebook | spark | 1 | 8888 | 1Gi PVC | `jupyter.local` (Ingress) |
| **Kafka Controller** | Strimzi / Kafka 4.2.0 | kafka | 1 | — | 100Gi PVC | Internal only |
| **Kafka Broker** | Strimzi / Kafka 4.2.0 | kafka | 1 | 9092/9093 | 100Gi PVC | Internal only |
