---
name: Architecture decisions 2026-04-09
description: Foundational target-state decisions for the satellite telemetry data+ML platform design
type: project
---

Target-state technology choices locked in during the 2026-04-09 architecture design session, on top of the existing Spark/Iceberg/MinIO/Postgres/Kafka/Strimzi/JupyterLab stack:

- Feature store: Feast with Iceberg offline store + Redis online store; Feast registry in shared-services Postgres
- Experiment tracking + model registry: MLflow; metadata in shared-services Postgres, artifacts in MinIO bucket `mlflow-artifacts`
- Distributed training: Spark MLlib as default track; KubeRay + PyTorch as Phase 5 track for sequence/DL models. Kubeflow Training Operator rejected as redundant with Ray.
- Online serving: KServe (raw mode on OrbStack). Seldon v2 rejected due to operational surface + licensing churn. BentoML/Triton can be wrapped as KServe runtimes if needed.
- Orchestration: **Dagster** (asset-oriented, matches Iceberg lakehouse 1:1). Backend in shared-services Postgres (`dagster` db). Changed from Airflow on 2026-04-09 at user request — user dislikes Airflow. Temporal was also suggested but rejected: it is a durable-execution engine for code workflows, not a data-asset orchestrator, and lacks Spark/Iceberg/OpenLineage/partition-backfill primitives this platform needs. Keep Temporal in mind for future command-and-control / cross-system workflow use cases.
- Lineage: OpenLineage + Marquez — treated as non-optional for the mission-critical posture.
- Data quality: Great Expectations over Soda Core (stronger Spark integration).
- Drift monitoring: Evidently (in-cluster) over WhyLabs (SaaS push).
- Schema registry: Apicurio over Confluent (fully Apache 2.0).
- Observability: kube-prometheus-stack + Loki + Tempo + OTel Collector. ELK rejected.
- HBase: formally retire. Redis + KServe cover the low-latency lookup use case on a single-node cluster.
- Telemetry TSDB: none — store in Iceberg with `days(event_timestamp) + bucket(16, spacecraft_id)` partitioning and sort on `(spacecraft_id, subsystem, metric_name, event_timestamp)`. Redis caches last ~15 min for live dashboards. VictoriaMetrics is the escape hatch if Iceberg query latency misses SLO.
- Iceberg maintenance: non-optional daily Dagster asset job (rewrite_data_files, rewrite_manifests, expire_snapshots, remove_orphan_files weekly). Must be separate ops with independent retries, not bundled.
- Streaming microbatch: recommend reducing bronze hop from 300s to 60s; keep larger intervals for silver→gold aggregations.
- Anomaly detection: two-stage — always-on rule-based streaming job + ML-based streaming+batch. Rule-based must not depend on ML model being up.
- Namespaces to add: observability, orchestration, ml-train, ml-serve, ml-platform.
- Postgres reuse policy: every new metadata store (MLflow, Airflow, Feast registry, Apicurio) gets a new database in the existing shared-services Postgres. Do NOT add new Postgres instances.

**Why:** These decisions collectively minimize operational surface on a single-node OrbStack cluster while preserving a credible migration path to a real production cluster, and they establish reproducibility + auditability primitives (Iceberg snapshot pinning, OpenLineage, MLflow) suitable for a mission-critical posture.

**How to apply:** Treat these as the default answers for any future question on this repo's data/ML platform. Deviations require explicit justification — especially the "reuse shared-services Postgres", "Iceberg-only for time series", and "retire HBase" decisions, which are the most likely to be re-litigated.
