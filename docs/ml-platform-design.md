# Modern Data Platform Design — ML + Space Telemetry

**Date:** 2026-04-09
**Status:** Design proposal (research only — no implementation yet)
**Authors:** Three-agent design review: Principal Architect (Opus), Devil's Advocate, Space ML Scientist

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Design Principles](#2-design-principles)
3. [Target Architecture](#3-target-architecture)
4. [ML Training Pipeline](#4-ml-training-pipeline)
5. [ML Model Serving](#5-ml-model-serving)
6. [Space Telemetry Architecture](#6-space-telemetry-architecture)
7. [Lakehouse Layer Design](#7-lakehouse-layer-design)
8. [Platform Services (Observability, Quality, Security)](#8-platform-services)
9. [Space Domain Analysis — Scientist Perspective](#9-space-domain-analysis--scientist-perspective)
10. [ML Workflow Requirements — Scientist Perspective](#10-ml-workflow-requirements--scientist-perspective)
11. [Critical Risk Analysis — Devil's Advocate](#11-critical-risk-analysis--devils-advocate)
12. [Implementation Roadmap](#12-implementation-roadmap)
13. [Component Delta: What to Add vs. What Exists](#13-component-delta-what-to-add-vs-what-exists)

---

## 1. Executive Summary

The existing platform (Spark + Iceberg + MinIO + Kafka + JupyterLab + ArgoCD on OrbStack) is a solid foundation. The core pipeline — satellite simulator → Kafka → Spark Structured Streaming → Iceberg — is sound and operationally coherent.

This document designs the expansion to support:
- **ML training pipelines** with reproducible experiment tracking, feature stores, and distributed training
- **ML model serving** with a registry, online/batch inference, canary deployments, and drift monitoring
- **Space telemetry processing** with medallion lakehouse layers, anomaly detection, and hot/warm/cold tiering

Three perspectives inform this design:

**The architect** found that every new component can and should be built on existing Iceberg, Spark, Kafka, MinIO, and PostgreSQL — no new storage primitives are needed. The additions (MLflow, KServe, Feast, Dagster, Prometheus/Grafana, OpenLineage) extend the stack without forking it. Iceberg's snapshot isolation is the correct primitive for training-data reproducibility and replaces DVC. PostgreSQL (already present) serves as backend for MLflow, Airflow, and Feast — no additional databases needed.

**The devil's advocate** found that the stack is already more complex than its current use cases justify. The 300s microbatch is batch processing wearing streaming clothes. HBase at 0 replicas is dead weight that should be deleted. A feature store, A/B testing, and drift detection add enormous ops burden before a single model exists. The most likely failure mode is building infrastructure for problems the platform does not yet have.

**The scientist** found the hardest problems are not infrastructure: they are domain problems. Real satellite telemetry has binary CCSDS encoding, clock drift, data gaps from ground station passes, a label scarcity problem (600:1 class imbalance or worse), and physics constraints (orbital phase, eclipse transitions) that no generic MLOps framework accounts for. Spark is too slow for exploratory analysis — scientists will default to Pandas/Polars locally and bypass the stack until training time. Experiment tracking (MLflow) and reproducibility (Iceberg snapshot pinning) are the highest-leverage first investments.

**Recommended build order:** pipeline first → one trained model → simple serving → operational hardening.

---

## 2. Design Principles

1. **Reliability before performance, performance before cost.** Telemetry loss is unacceptable; replay must always be possible from Kafka or the Iceberg bronze layer.
2. **Extend before adding.** Spark, Iceberg, Kafka, MinIO, PostgreSQL, and ArgoCD already exist. Every new component must justify itself against reusing what is already there.
3. **GitOps is the control plane.** Any runtime-mutable state (models, features, experiments) must have a Git-declared backing store. No click-ops.
4. **Iceberg is the single source of truth.** Features, training sets, predictions, and ground-truth labels all land as Iceberg tables. This gives time-travel, snapshot isolation, and a unified lineage substrate.
5. **Provenance is non-negotiable.** Every model artifact must be traceable to: (a) an Iceberg snapshot ID, (b) a git SHA, (c) a container image digest, (d) an experiment run ID. This is table stakes for space-system workloads and aligns with ITAR/EAR auditability expectations.
6. **Two-tier design for safety-critical paths.** Rule-based detectors are always the primary safety net. ML models augment but never replace deterministic checks for space operations.
7. **Build for actual pain.** Do not build a feature store before features are defined. Do not build drift detection before a model exists. Infrastructure serves the model, not the reverse.

---

## 3. Target Architecture

### High-Level System View

```
                        ┌─────────────────────────────────────┐
                        │          Ground Segment (sim)        │
                        │  Satellite Simulator                 │
                        │       ↓ JSON/Avro                    │
                        │  Kafka (Strimzi KRaft)               │
                        │   ├─ satellite-telemetry             │
                        │   ├─ satellite-events                │
                        │   ├─ anomaly-alerts                  │
                        │   └─ ml-inference-logs               │
                        └──────────────────┬──────────────────┘
                                           │
               ┌───────────────────────────┴──────────────────────────┐
               │              Stream Processing (Spark SS)            │
               │   Rule-based anomaly (60s) + bronze ingest (60s)    │
               │   ML online scoring (via KServe gRPC)               │
               └───────────────────────────┬──────────────────────────┘
                                           │
               ┌───────────────────────────┴──────────────────────────┐
               │             Lakehouse — Iceberg on MinIO             │
               │  bronze.*   silver.*   gold.*                        │
               │  features.*   ml.*   audit.*                         │
               │  (catalog metadata → PostgreSQL / Iceberg REST)      │
               └──┬──────────────┬─────────────┬──────────────────────┘
                  │              │             │
          ┌───────▼──────┐ ┌────▼──────┐ ┌────▼───────────┐
          │  Feast       │ │ Spark     │ │  MLflow        │
          │  Offline:    │ │ Training  │ │  Tracking +    │
          │   Iceberg    │ │ (MLlib)   │ │  Registry      │
          │  Online:     │ │  + Ray    │ │  (Postgres +   │
          │   Redis      │ │ (optional)│ │   MinIO)       │
          └───────┬──────┘ └────┬──────┘ └────┬───────────┘
                  │             │             │
                  │             └─────────────┘
                  │                    │ model artifacts
                  │                    ▼
                  │             ┌──────────────┐
                  └────────────►│  KServe      │ ← online inference
                                │  (ml-serve)  │    canary / shadow
                                └──────┬───────┘
                                       │ predictions
                                       ▼
                               Iceberg: ml.predictions
                                       │
                               Evidently drift reports
                               → Prometheus → Grafana
```

### Namespace Plan (additions to existing)

| Namespace | New Components |
|-----------|---------------|
| `ml-platform` | MLflow tracking server, Marquez (lineage), Great Expectations |
| `ml-serve` | KServe controller, InferenceService pods |
| `ml-train` | Ray (KubeRay) training workers (optional, for deep learning) |
| `orchestration` | Dagster (webserver, daemon, user-code deployment) |
| `monitoring` | Prometheus, Grafana, Loki, Tempo, Alertmanager |
| `data-warehouse` | +Feast (online store: Redis), +Apicurio Schema Registry |
| `shared-services` | +Redis (Bitnami chart) |

---

## 4. ML Training Pipeline

### 4.1 Feature Store — Feast (Iceberg Offline + Redis Online)

**Choice:** Feast open source with a pluggable Iceberg offline store and Redis online store.

**Alternatives considered and rejected:**
- **Tecton** — SaaS/commercial, incompatible with self-hosted GitOps lab
- **Hopsworks** — brings its own metastore and duplicates Iceberg; heavyweight
- **Roll-your-own** — loses point-in-time join semantics and feature versioning; not worth it

**Offline store:** Iceberg tables under the `features.*` namespace, one table per feature view. Schema per table: `entity_id, event_timestamp, created_timestamp, feature_1..N`. Partition by `days(event_timestamp)`, sort by `entity_id`. The `event_timestamp` / `created_timestamp` pairing is the single most important schema decision — it enables correct point-in-time joins that prevent label leakage.

**Online store:** Redis (single-node Bitnami chart in `shared-services` namespace). Latency target <5 ms p99 for single-entity lookups. Materialization (Iceberg → Redis) runs every 5 minutes for hot telemetry features and every 1 hour for aggregate features.

**Feature registry backend:** the existing PostgreSQL in `shared-services` with a new `feast_registry` database. Do not add another Postgres instance.

**Satellite domain entities:**
- `spacecraft_id` — primary flight entity
- `subsystem_id` — `(spacecraft_id, subsystem)` composite (power, thermal, ADCS, comms, payload)
- `orbit_pass_id` — time-bounded entity for per-pass aggregates

**Feature view examples (inputs from gold layer):**
- `spacecraft_health_5m` — rolling 5-minute mean/std/min/max of battery voltage, bus current, panel temperatures
- `subsystem_health_1h` — hourly aggregates, OOL counts, anomaly score rolling average
- `orbit_pass_summary` — per-pass eclipse duration, attitude stability index, charge recovery rate

**When is a feature store NOT worth it?** The devil's advocate correctly identifies that Feast is premature when:
- A single person builds and maintains all models
- Models retrain infrequently (monthly)
- Features are cheap to recompute
- No training-serving skew has been observed

Defer Feast implementation until there are two models sharing the same features and recomputing them is measurably painful.

### 4.2 Training Data Versioning

**Decision: Iceberg snapshots as the versioning primitive. No DVC, no LakeFS.**

Every training run pins to a specific Iceberg snapshot ID per input table, using:
```sql
SELECT * FROM features.spacecraft_health_5m VERSION AS OF <snapshot_id>
```

MLflow logs for each run: `(catalog, namespace, table_name, snapshot_id)`. This combination gives:
- **Bit-exact reproducibility** — re-running the same run ID reads the same bytes regardless of subsequent table changes
- **Blast-radius isolation** — corrupt ingest does not affect runs already in flight
- **Audit trail** — a mission operator or regulator can ask "what data was used to train model X" and receive a deterministic answer

**Training set materialization:** for expensive point-in-time correct joins (feature + label join), materialize a frozen training table as `ml.training_sets.<model>_<run_id>`. Retain indefinitely — storage cost is lower than reproducing the join.

**Labels:** anomaly labels land in `silver.anomaly_labels` with columns `spacecraft_id, event_timestamp, anomaly_type, confidence, label_source (rule_based | operator | retrospective), labeled_by, labeled_at`.

### 4.3 Experiment Tracking — MLflow

**Choice:** MLflow OSS (tracking server + model registry).

**Why not W&B / Neptune:** W&B is SaaS-first, raises data residency concerns for telemetry (ITAR-adjacent), and requires internet access. Neptune has a smaller community. MLflow is the de facto open standard, integrates natively with Spark MLlib, PyTorch, XGBoost, and KServe.

**Backend configuration:**
- Metadata store: PostgreSQL in `shared-services`, new database `mlflow`
- Artifact store: MinIO bucket `mlflow-artifacts`, path-style access, `AWS_REGION` set

**What every training run must log:**
- Git SHA of training code
- Container image digest of the trainer
- Input Iceberg snapshot IDs (feature tables + label tables)
- Hyperparameters, metrics, confusion matrix, calibration curves, precision-recall curve
- Model artifact + `pip freeze` environment specification
- Data quality report (Great Expectations result — see §8.2)
- OpenLineage run ID (for bidirectional traceability with Marquez)

### 4.4 Distributed Training

**Two-track strategy — choose based on model type:**

**Track A — Spark MLlib (default for classical models):** Isolation Forest, Random Forest, GBT on tabular telemetry features. Reuses 100% of existing infrastructure. Training runs as Spark applications submitted via Spark Connect or `spark-submit` on Kubernetes. Reads training datasets from Iceberg.

**Track B — Ray on Kubernetes / KubeRay (for deep learning):** LSTM/Transformer models for sequence anomaly detection, VAE for unsupervised novelty detection. Ray Train handles PyTorch DDP; Ray Tune handles hyperparameter search. Ray Data reads training data from Iceberg via PyArrow (bypasses JVM entirely). KubeRay operator required.

**Devil's advocate warning:** On a single-node OrbStack cluster, distributed training is theater — there is no parallelism across physical machines. Ray on a single node is more complex than plain PyTorch in a Jupyter cell and provides no throughput benefit. Add KubeRay when you have a multi-node cluster or a concrete time-to-train SLO that single-node training violates.

**Scientist recommendation for early phases:** plain scikit-learn or PyTorch in JupyterLab for model development. Spark only for preprocessing and batch scoring. Ray only when the model architecture genuinely requires distributed computation.

### 4.5 Orchestration and Lineage

**Orchestration: Dagster** (Helm chart `dagster/dagster`, `orchestration` namespace)

Backend: `shared-services` PostgreSQL, database `dagster` (holds run storage, event log, and schedule storage — Dagster requires a single Postgres DB for all three).

**Why Dagster over Airflow:** Dagster's asset-oriented model matches the Iceberg lakehouse 1:1 — each Iceberg table (`bronze.telemetry_raw`, `silver.telemetry_normalized`, `gold.spacecraft_health_1m`, `features.*`, `ml.predictions.*`) is a first-class *software-defined asset* with declared upstream dependencies. This collapses three things Airflow keeps separate: the DAG, the lineage graph, and the data catalog. Partitioned assets (by `days(event_timestamp)`) make telemetry backfills a first-class operation rather than a bespoke DAG pattern. Dagster also emits OpenLineage natively and has well-maintained integrations for Spark (`dagster-pyspark`, `dagster-spark`), dbt, Great Expectations, MLflow, and Papermill — which cover every job this platform needs.

**Temporal was considered and rejected:** it is a durable-execution engine for code-defined workflows (sagas, long-running transactional business processes), not a data-asset orchestrator. It has no native scheduling-of-data-pipelines ergonomics, no Spark/Iceberg/dbt operators, no OpenLineage integration, and no partition/backfill model. Keep Temporal in mind for a future command-and-control use case (ground-station tasking, cross-system model-promotion workflows) — not for this platform.

**Asset groups and jobs:**

| Asset group | Contents | Scheduling |
|-------------|----------|------------|
| `telemetry_lakehouse` | `bronze.*`, `silver.*`, `gold.*` assets backed by Spark jobs | Event-driven via sensors on Spark SS checkpoints |
| `iceberg_maintenance` | Compaction, snapshot expiry, orphan cleanup, manifest rewrite — one op per operation | Schedule: daily 02:00 UTC |
| `features` | Feast feature views materialized from `gold.*` → Redis | Schedule: 5m hot features, 1h aggregates |
| `ml_training_<model>` | Training set materialization → MLflow run → model registry promotion | Manual launchpad + schedule |
| `batch_inference_<model>` | `features.*` → model pyfunc → `ml.predictions.<model>` | Schedule: nightly |
| `drift_report` | `ml.predictions` + `silver.anomaly_labels` → Evidently → `ml.drift_reports` | Schedule: daily |
| `tiering` | Iceberg → hot/warm/cold bucket moves via table-property-driven ops | Schedule: weekly |

Each maintenance operation is a distinct Dagster op with independent retry policy — bundling compaction, snapshot expiry, and orphan cleanup into a single op causes a long-running `remove_orphan_files` to block critical `rewrite_data_files` on failure.

**User code deployment:** pipeline code ships as a container image (built in CI, pushed to ghcr.io) referenced by a `user-deployments` entry in the Dagster Helm values — the same GitOps flow already used for Spark. No click-ops.

**Lineage: OpenLineage + Marquez**

OpenLineage events are emitted by Spark jobs automatically via the `io.openlineage:openlineage-spark` listener JAR (baked into the existing custom Spark image). Dagster emits OpenLineage events natively via `dagster-openlineage`, and — critically — Dagster's own asset graph already encodes most of what Marquez would show. Marquez remains useful as a unified cross-system lineage view (Spark + Dagster + any future non-Dagster producers) and as a long-retention audit store independent of the Dagster run database. It visualizes the full DAG: Kafka topic → bronze table → silver table → feature view → training set → model → prediction table.

This is the single most important observability addition for space/regulated operations — full provenance of "what produced this prediction" is required for operator trust and post-incident review.

---

## 5. ML Model Serving

### 5.1 Model Registry — MLflow Model Registry

Already included with MLflow (§4.3). Promotion stages: `None → Staging → Production → Archived`.

Promotion to Production requires:
1. A passing evaluation report (confusion matrix, AUC > threshold) logged to the MLflow run
2. A git-committed approval file at `ml-promotions/<model>/<version>.yaml` in this repo
3. ArgoCD sync to apply the updated KServe `InferenceService` manifest

This gives a four-eyes, auditable promotion path without a custom UI. The ArgoCD audit log records who approved the git change and when.

### 5.2 Online Inference — KServe

**Choice:** KServe over Seldon Core v2 and BentoML standalone.

**Why KServe:**
- First-class MLflow integration — a registered model deploys as a KServe `InferenceService` with ~10 lines of YAML, `storageUri` pointing to the MinIO artifact path
- Native canary traffic splitting via `canaryTrafficPercent` in the CRD
- Raw deployment mode (no Knative/Istio overhead) is appropriate for OrbStack's resource constraints
- v2 inference protocol (REST + gRPC), with gRPC preferred for internal callers for latency

**Why not Seldon Core v2:** excellent but operationally heavier; v1/v2 ecosystem is fragmented; BSL licensing on some components.

**Why not BentoML standalone:** great packaging DX but lacks the Kubernetes-native deployment CRD, canary, and autoscaling.

**Serving path for online anomaly detection:**
```
Kafka consumer → Spark SS (feature extraction) → Redis (feature lookup via Feast) 
→ KServe gRPC call → anomaly score → Kafka `anomaly-alerts` topic
```

A KServe "transformer" sidecar fetches online features from Redis before calling the predictor, keeping inference latency low while decoupling feature computation from scoring.

### 5.3 Batch Inference

Batch scoring runs as Spark jobs orchestrated by Dagster (as the `batch_inference_<model>` asset group). Input: Iceberg `features.*` tables. Output: Iceberg `ml.predictions.<model_name>`. Each prediction row carries: `prediction_id, entity_id, event_timestamp, model_name, model_version, prediction_label, anomaly_score, feature_snapshot_id`.

Writing predictions to Iceberg (not a separate store) is deliberate: predictions become first-class lakehouse data joinable against ground-truth labels for drift and calibration analysis.

### 5.4 A/B Testing and Canary Deployments

**KServe canary rollout:** update `canaryTrafficPercent` in the InferenceService YAML in git → ArgoCD syncs → KServe shifts traffic → observe metrics in Grafana → promote or rollback via git.

**Shadow mode (recommended default for space-health models):** KServe mirrors live traffic to the new model version, but its predictions write only to `ml.predictions.shadow_<model>`. Operators compare shadow predictions to production predictions offline. No production impact until the shadow model is explicitly promoted. This is the correct default posture for any model influencing spacecraft health alerts — live canary on satellite monitoring is too high risk.

**A/B analysis:** request-level logs flow to Kafka `ml-inference-logs` → Iceberg `ml.inference_logs` → scheduled Dagster Papermill asset comparing cohort-level precision/recall between model versions.

### 5.5 Model Monitoring and Drift Detection

**Three-layer monitoring:**

**Layer 1 — Service health:** Prometheus scrapes KServe `/metrics`: RPS, latency p50/p95/p99, error rate. SLO alert if p99 > 100ms or error rate > 1%.

**Layer 2 — Input data drift:** Daily Dagster job compares live inference feature distributions against training-set reference (stored as MLflow artifacts) using PSI (Population Stability Index) and KS tests. Alert fires when PSI > 0.2 on any top-10 feature. Results land in `ml.drift_reports`.

**Layer 3 — Prediction/performance drift:** Compare `ml.predictions` against delayed ground-truth labels in `silver.anomaly_labels`. Label delay for satellite anomaly detection is real — most labels arrive hours to days later from operator review. Monitoring must separate input drift (immediate) from performance degradation (delayed). Evidently AI runs fully in-cluster with no SaaS dependency.

**Critical domain caveat (from scientist):** Standard drift detection assumes unexpected distribution shifts are bad. Spacecraft telemetry violates this — distributions change predictably with orbital phase, eclipse entry/exit, and attitude maneuvers. These are not drift. A model flagging "eclipse battery voltage drop" as input drift will generate constant false alerts. Drift baselines must be conditioned on operational mode (`in_eclipse`, `safe_mode`, `nominal`) before any drift metric is meaningful for space data.

---

## 6. Space Telemetry Architecture

### 6.1 Telemetry Ingestion

**Kafka topic design (additions to the existing `satellite-telemetry`):**

| Topic | Partitions | Retention | Purpose |
|-------|-----------|-----------|---------|
| `satellite-telemetry` | 12 (by `spacecraft_id`) | 7 days | Raw frames from simulator |
| `satellite-events` | 6 | 30 days | Mode changes, command acknowledgments |
| `anomaly-alerts` | 3 | 90 days | Rule-based + ML anomaly output |
| `ml-inference-logs` | 6 | 14 days | Online inference request/response |

Partitioning by `spacecraft_id` guarantees per-satellite ordering, which matters for stateful streaming computations (windowed aggregates, stateful anomaly detection, sequence models).

**Recommended ingest changes:**
1. **Add Apicurio Schema Registry** (OSS, Apache 2.0, backed by `shared-services` Postgres). Schema enforcement prevents one bad producer from breaking the entire pipeline. Move producers to Avro or Protobuf with registry references.
2. **Reduce bronze microbatch from 300s → 60s.** Small-file overhead at 60s is manageable with proper compaction (§7.2). This tightens end-to-end latency by 4 minutes for the hot anomaly path.
3. **Keep 300s (or larger) trigger for silver→gold aggregations** where latency matters less.

### 6.2 Medallion Lakehouse Layers for Telemetry

**Bronze — `bronze.satellite_telemetry_raw`**
- Append-only, never modified. Immutable audit log.
- Schema: raw frame as received + `kafka_partition, kafka_offset, kafka_timestamp, ingest_ts`
- Partition: `days(kafka_timestamp)`
- Retention: 90 days

**Silver — `silver.telemetry_normalized`**
- Parsed, typed, unit-normalized, deduplicated by `(spacecraft_id, event_timestamp, metric_name)`
- Deduplication handles frame retransmissions from multiple ground stations
- Schema: `spacecraft_id, subsystem, metric_name, value, unit, quality_flag, operational_mode, in_eclipse, orbit_pass_id, event_timestamp, ingest_ts`
- Partition: `days(event_timestamp), bucket(16, spacecraft_id)`
- Sort order within files: `(spacecraft_id, subsystem, metric_name, event_timestamp)`
- Retention: 2 years

**Gold — `gold.*`**
- `gold.spacecraft_health_1m` — 1-minute downsampled aggregates per spacecraft
- `gold.subsystem_health_5m` — 5-minute subsystem-level aggregates
- `gold.orbit_pass_summary` — per-pass KPIs (eclipse duration, pass quality, charge recovery rate)
- Direct inputs to Feast feature views
- Partition: `days(event_timestamp)`
- Retention: 2 years

### 6.3 Time-Series Storage Strategy

**Decision: Iceberg only. Do not introduce a dedicated TSDB (InfluxDB, TimescaleDB, VictoriaMetrics).**

Rationale: Adding a TSDB introduces a second source of truth, a second query engine, and a second retention policy — this is the #1 operational hazard in telemetry platforms. Iceberg handles multi-TB time-series correctly when partitioned and sorted as specified in §7.1.

**The one genuine Iceberg weakness:** sub-second point lookups for live dashboards. Mitigation: serve the last N minutes from Redis (populated by the streaming job), which plays double duty as the online feature store AND the hot telemetry cache. Everything older comes from Iceberg.

**Escape hatch:** if Iceberg cannot meet dashboard latency SLOs (measure first), the fallback is VictoriaMetrics (not Influx — simpler, lower resource) fed from the same Kafka topic for a 7-day hot window, leaving Iceberg authoritative for everything else. Defer until measured.

### 6.4 Anomaly Detection Pipeline (Two-Tier)

**Tier 1 — Rule-based (always-on safety net):**
A Spark Structured Streaming job reads `satellite-telemetry`, evaluates per-metric thresholds and rate-of-change rules from a Git-committed rules YAML, and writes violations to `anomaly-alerts` topic and `silver.anomaly_rule_hits` Iceberg table. Latency: ~1 minute. This tier must not depend on any ML model — it is the hard backstop.

**Tier 2 — ML-based (statistical augmentation):**
- *Online path:* Spark SS job pulls features from Redis (Feast), calls the KServe InferenceService over gRPC, writes scores to `ml.predictions.anomaly_live` and alerts above threshold to `anomaly-alerts`. Latency: ~5–10s after features are ready.
- *Batch path:* Nightly Dagster job re-scores the full day's data with the latest model version for backfill and drift analysis.

**Why two tiers:** In space operations, you never want a single point of failure in anomaly detection. The rule-based tier catches obvious out-of-bounds conditions even if the ML system is down, stale, or under retraining. The ML tier catches subtle multivariate drifts that rules miss. Both write to `gold.anomaly_events` for unified post-hoc analysis.

**Domain requirement from scientist:** Anomaly detection must be conditioned on operational mode. A battery voltage drop during eclipse is nominal. The same drop in sunlight during NOMINAL mode is a fault. `operational_mode` and `in_eclipse` must be features in every anomaly model. Without this conditioning, false alert rates will be unacceptably high.

### 6.5 Hot / Warm / Cold Tiering

| Tier | Age | Storage | Query Pattern |
|------|-----|---------|--------------|
| **Hot** | 0–15 min | Redis | Live dashboards, online inference |
| **Warm** | 15 min – 30 days | MinIO (compacted Parquet) | Interactive analytics, training |
| **Cold** | 30 days – 2 years | MinIO (separate bucket `telemetry-cold`) | Audit, backfill training |
| **Frozen** | 2+ years | External glacier-class storage | Regulatory retention only |

Tiering is implemented via Iceberg + S3 lifecycle rules on MinIO. The MinIO `telemetry-cold` bucket has higher compression targets and larger file sizes (512MB). Tiering decisions are encoded as Iceberg table properties and executed by a weekly Dagster job in the `tiering` asset group.

### 6.6 Retention and Compaction Policy

Compaction is **not optional** for a streaming sink. At 60s microbatch, each silver table accumulates ~1,440 small files/day. Without compaction, query performance degrades within a week.

**Dagster job `iceberg_maintenance` (asset group of the same name) — daily at 02:00 UTC:**

| Step | Target | Operation |
|------|--------|-----------|
| 1 | All bronze/silver tables, last 24h | `rewrite_data_files` bin-pack, target 256MB |
| 2 | Tables with >20 manifest files | `rewrite_manifests` |
| 3 | All tables | `expire_snapshots` (bronze: keep 7d, silver: 30d, gold: 90d) |
| 4 | All tables (Sundays only) | `remove_orphan_files` with 7-day safety window |
| 5 | Tables using MoR delete | `rewrite_position_deletes` |

**Critical note:** each maintenance operation must run as a distinct Dagster op with its own retry policy. Bundling them into a single op causes long-running `remove_orphan_files` to block critical `rewrite_data_files` on failure.

---

## 7. Lakehouse Layer Design

### 7.1 Partitioning Strategy

```
bronze.satellite_telemetry_raw:
  PARTITION BY (days(kafka_timestamp))
  SORT BY (spacecraft_id, kafka_offset)
  write.target-file-size-bytes = 134217728   -- 128 MB

silver.telemetry_normalized:
  PARTITION BY (days(event_timestamp), bucket(16, spacecraft_id))
  SORT BY (spacecraft_id, subsystem, metric_name, event_timestamp)

gold.spacecraft_health_1m:
  PARTITION BY (days(event_timestamp))
  SORT BY (spacecraft_id, event_timestamp)

features.spacecraft_health_5m:
  PARTITION BY (days(event_timestamp))
  SORT BY (entity_id, event_timestamp)
```

**Key decisions:**
- **Hidden partitioning** so analysts never write predicates on derived partition columns
- **Z-order / sort order** on `(spacecraft_id, event_timestamp)` enables Iceberg's data-file-level min/max predicate pushdown for the dominant query shape: "metric X on spacecraft Y over time window T"
- **Days-level partitioning** not hours — 24× more metadata at hours-level without proportional query benefit for this data volume
- **Bucket(16, spacecraft_id)** distributes writes and enables predicate pushdown on `spacecraft_id = ?`; revisit bucket count at 50+ spacecraft

### 7.2 Table Maintenance

See §6.6. Key addition: maintenance jobs must emit metrics to Prometheus (files compacted, bytes reclaimed, snapshot count, orphan bytes removed). Compaction SLO: no partition should exceed 1000 small files before the next maintenance window.

### 7.3 Multi-Table Transaction Patterns

Iceberg does not support cross-table ACID transactions. Compensating patterns:

1. **Outbox pattern for Kafka → Iceberg hop.** Kafka offsets stored in Spark SS checkpoint are the transactional boundary. Sink is idempotent via MoR merge on `(spacecraft_id, event_timestamp, metric_name)`.
2. **Consistent snapshot tagging.** When a batch job writes multiple output tables (e.g., gold + feature tables), tag all resulting snapshots with the same `run_id` using Iceberg's tag feature. Downstream readers query `FOR VERSION AS OF TAG 'run_<id>'` on each table.
3. **Staging + atomic swap.** Write to `gold.<table>_staging`, validate, then use `CALL system.fast_forward` to promote atomically. Used for daily aggregates where correctness must be verified before publication.
4. **Iceberg branches for data quality gating.** Write to an `audit` branch, run Great Expectations checks, fast-forward to `main` only if checks pass. This is the cleanest primitive for "publish only if valid."

### 7.4 Schema Evolution for Sensor Data

- **Additive only (new columns):** safe, metadata-only, zero migration cost. New sensors come online frequently — this must be the default path.
- **Column renames:** use Iceberg's column rename by field ID (not drop + add). Drop + add loses historical data association.
- **Type widening:** `int → long`, `float → double` are safe. Narrowing is forbidden.
- **Schema registry alignment:** Apicurio schemas and Iceberg schemas are kept in sync by a Spark validation job that reads the registry and asserts the bronze table schema is a superset.
- **CI enforcement:** a CI job validates proposed schema changes against Iceberg compatibility rules before any Helm chart PR merges.

---

## 8. Platform Services

### 8.1 Observability

**Metrics: kube-prometheus-stack (Prometheus + Grafana + Alertmanager)**
- Spark metrics: enable Prometheus servlet in the existing custom Spark image
- Kafka metrics: Strimzi exports natively via JMX exporter
- MinIO: native Prometheus endpoint
- PostgreSQL: `postgres-exporter` sidecar
- KServe: native `/metrics` endpoint
- Custom business metrics: rows ingested/s, Iceberg snapshot age, compaction backlog, feature freshness, drift scores

**Tracing: OpenTelemetry Collector + Tempo**
- Trace the full inference path: Ingress → KServe transformer → Redis/Feast → predictor → response
- Spark job traces via OpenLineage double as lineage + distributed tracing

**Logging: Loki + Promtail**
- Lightweight, integrates natively with Grafana (single UI for logs + metrics + traces)
- Lower resource footprint than Elasticsearch for this scale

**Key Grafana dashboards:**
- Telemetry ingestion throughput and lag
- Iceberg table health (file counts, snapshot age, compaction status)
- ML model serving latency and error rates
- Anomaly detection precision/recall over time
- Feature freshness per view
- Drift report summary

### 8.2 Data Quality

**Choice: Great Expectations (OSS)**

Wired into Dagster as an asset check on every asset that writes to silver or gold layers (via the `dagster-ge` integration). Failed expectations fail the materialization, preventing downstream assets from running. Key expectation suites:

| Suite | When it runs | Key checks |
|-------|-------------|------------|
| `bronze_schema` | After every bronze write | Schema matches registry, no null spacecraft_id, event_time not in future |
| `silver_completeness` | After silver normalization | <5% null quality_flag, expected channels present per spacecraft |
| `feature_freshness` | Before training run | Feature tables have data within last N hours |
| `training_data` | At training job start | Class balance within expected ratio, snapshot exists, row count within 10% of expected |

Failed checks abort the pipeline and log to MLflow as a failed run — they do not silently produce a bad model.

### 8.3 Access Control and Namespace Isolation

Current namespace assignments (unchanged): `default`, `non-prod`, `data-warehouse`, `shared-services`, `spark`, `kafka`, `satellite`.

**New namespace isolation for ML:**
- `ml-platform` — read access to all Iceberg tables, write access to `ml.*` namespace only
- `ml-serve` — read access to `ml.*` and `features.*`, no write access to lakehouse
- `ml-train` — read access to `features.*`, write access to `ml.training_sets.*`
- `orchestration` — full access (Dagster coordinates all namespaces)

**Sealed Secrets:** all new credentials (MLflow DB password, Redis password, KServe ServiceAccount tokens) follow the existing SealedSecret + kubeseal pattern. No new credentials management approach introduced.

---

## 9. Space Domain Analysis — Scientist Perspective

### 9.1 What Real Satellite Telemetry Looks Like

The simulator captures the essential structure: a stream of housekeeping (HK) packets containing scalar sensor readings from multiple subsystems at regular rates. However, real satellite telemetry differs in critical ways:

**CCSDS binary encoding.** Real telemetry arrives as raw binary CCSDS packets, not JSON. Each packet contains a primary header (APID, 14-bit sequence count, CDS timestamp) and mission-specific engineering values packed in binary. Decommutation — the process of unpacking parameter values from binary bytes — requires a mission-specific telemetry database (SCOS-2000 `.mib` for ESA missions, XTCE for NASA GSFC). This layer does not exist in the current platform and would be the first major addition for real satellite integration.

**Typical telemetry channels for a LEO satellite:**
- Power: battery voltage (V), solar array current (A) per panel, regulated bus voltage, state of charge (%)
- Thermal: temperatures at 10–30 structural points (solar panels, battery, reaction wheels, star trackers, instrument focal planes)
- Attitude: quaternion, angular velocity from gyroscopes, star tracker validity flags, reaction wheel speeds and temperatures
- Communications: RSSI, bit error rate, uplink/downlink frame counts
- Payload: instrument mode, detector temperature, image acquisition count

**Non-uniform sampling rates.** Attitude quaternion: 10 Hz. Battery voltage: 0.1 Hz. Tank pressure: 0.01 Hz. A platform that assumes uniform sampling per channel will compute incorrect rolling statistics and corrupt spectral features.

### 9.2 Time-Series Challenges

**Clock drift.** On-board clock drifts at rates of milliseconds per day. UTC reconstruction requires correlation with ranging data and time correlation packets. A channel sampled at "1 Hz" may exhibit effective sample intervals varying from 0.97 s to 1.03 s over 30 days — enough to corrupt spectral analysis assuming perfect stationarity. The platform must store both on-board time and ground-reconstructed UTC, not conflate them.

**Data gaps.** A single-ground-station mission has contact passes of 10–20 minutes per 90-minute orbit. Between passes, no data arrives. Gaps range from single-packet losses (sequence count jumps) to multi-hour outages (missed passes) to multi-day blackouts. Any ML model that does not explicitly model gaps will learn spurious patterns from gap boundaries (e.g., correlating "first packet after a gap" with anomalous readings, because temperatures genuinely behave differently post-eclipse emergence).

**Stuck sensors.** A failed sensor may report its last valid value indefinitely, producing a channel with anomalously low variance. Rolling variance below a physical noise floor is the standard detector. A platform that does not flag stuck sensors will train models on them as informative features.

**Retransmissions and duplicates.** Multiple ground stations receiving the same pass produce duplicate packets. Deduplication on `(spacecraft_id, event_timestamp, metric_name)` is required — already designed into the silver layer.

### 9.3 Labeling Challenges and the Imbalance Problem

**Label sources (from least to most useful):**
1. **Automated threshold violations:** structured but over-inclusive (nuisance alarms) and under-inclusive (gradual degradation stays within limits)
2. **Anomaly reports (ARs):** narrative free text in mission databases; require NLP or manual curation to extract structured labels
3. **Retrospective precursor labels:** expert engineers identify subtle pre-fault signatures in hindsight; most valuable for training but labor-intensive

**Class imbalance.** A healthy satellite produces one significant anomaly event per month. One year of 1-Hz telemetry = ~31 million samples. Anomalous samples: ~50,000. Imbalance ratio: 600:1 or worse. Accuracy and AUC are misleading at these ratios. Use precision-recall curves and carefully calibrated thresholds. Oversample anomaly windows or undersample nominal windows for training.

### 9.4 Physics Constraints That Cannot Be Automated Away

**Orbital phase as co-variate.** Battery voltage, solar power, and thermal readings are strongly periodic with the 90-minute orbit. A model ignoring orbital phase cannot distinguish orbital-phase-driven variation from anomalous behavior. Include `orbital_phase_rad`, `in_eclipse`, `minutes_since_eclipse_exit` as features in every model.

**Physics-model residuals as features.** Healthy cell voltage follows the Nernst equation (voltage-temperature coupling). Deviation from physics-model predictions is a stronger anomaly signal than the raw reading. Computing these residuals requires encoding mission-specific physics knowledge — it cannot be done generically.

**Operational mode context.** Safe mode, science mode, maneuver sequences each have distinct expected telemetry profiles. An anomaly detector without operational mode context generates constant false alerts during planned mode transitions.

**Subsystem coupling.** A battery temperature increase may cause current changes in the power subsystem, which may cause voltage changes detected by the attitude control system. Anomaly detection treating these as independent signals will miss correlated fault signatures and generate false positives on normal coupled behavior. Multi-variate models (VAE, TFT) handle this better than per-channel models.

### 9.5 Multi-Mission Schema Challenges

Different satellite missions use different parameter naming conventions, physical ranges, and anomaly taxonomies. A model trained on one mission cannot be applied to another without:
1. **Per-mission schema tables** in Iceberg (each mission has its own bronze/silver tables)
2. **A common normalized representation** for the ML feature space (standardized by physical unit and nominal range)
3. **Mission metadata tables** encoding per-mission calibration curves, nominal ranges, and operational mode definitions

This has not been designed into the current platform and should be treated as a future milestone rather than a day-one requirement.

---

## 10. ML Workflow Requirements — Scientist Perspective

### 10.1 The Experiment Lifecycle

A satellite telemetry anomaly detection project does not follow a tidy linear pipeline. In practice it spirals: the same phases repeat as understanding of the data deepens and the operational team's definition of "anomaly" evolves.

**Phase 1 — Data Archaeology (weeks 1–3)**
Plotting raw channels over time, identifying known anomaly periods from operations logs, correlating power readings with eclipse transitions, building intuition about which channels are informative vs. redundant. This is inherently exploratory, small-scale work. Spark is wrong here — 15–30 seconds per `.show()` call from Spark Connect makes tight feedback loops impossible. The right tool is Pandas or Polars with DuckDB, running locally in the notebook process.

**Phase 2 — Feature Experimentation (weeks 4–8)**
Rapid iteration across dozens of candidate features: rolling statistics, spectral transforms, cross-channel correlations, regime-conditional baselines. Each iteration is a notebook cell. Scientists will default to Pandas locally and bypass the Spark stack entirely at this phase. This is not a failure — it is correct behavior for the task. The Spark + Iceberg stack becomes relevant when feature computation needs to run at full-dataset scale.

**Phase 3 — Model Training and Evaluation (weeks 6–12, overlaps Phase 2)**
Train multiple model families, compare under time-ordered train/test splits (no temporal leakage). Log every run to MLflow. Evaluate on held-out labeled anomaly windows. The two-phase workflow: (1) develop and validate features on a small Pandas sample, (2) implement the feature engineering as a Spark + Iceberg job at full scale, (3) train from the materialized feature table.

**Phase 4 — Operational Integration (weeks 10–16)**
The model must run in near-real-time against the streaming pipeline. Feature engineering logic from the notebook must be promoted to a tested, versioned pipeline component. This transition is where most space ML projects break down. The platform must scaffold this promotion — notebook cells are not deployable.

### 10.2 Tooling Scientists Actually Need

| Need | Recommended Tool | Notes |
|------|-----------------|-------|
| Experiment tracking | MLflow (self-hosted) | ITAR-safe, integrates with Spark and KServe |
| Hyperparameter optimization | Optuna | Single-node, no Ray cluster needed for typical problem sizes |
| Interactive visualization | Plotly + HoloViews | Essential for telemetry time-series zoom/pan |
| Data profiling | ydata-profiling | One-call schema drift detection on new mission data |
| Notebook version control | nbstripout git filter | Strips outputs before commit; configure per-repo |
| Collaborative labeling | Label Studio (self-hosted) | UI for operator labeling of anomaly windows |
| Small-data exploration | DuckDB in Jupyter | SQL over local Parquet without Spark overhead |
| Feature engineering at scale | Spark + Iceberg | Step 2 only, after features are validated on small data |

### 10.3 Reproducibility Requirements

Minimum reproducibility standard for any model deployed to monitor a satellite:

1. **Training data pinned to Iceberg snapshot ID** — not a timestamp, a snapshot ID. Wall-clock timestamps are ambiguous if data was backfilled or corrected. Snapshot IDs are immutable pointers.
2. **Software environment fully specified** — a `pip freeze` output stored in the MLflow run. A Docker image digest is better. A `requirements.txt` alone is insufficient.
3. **Random seeds logged** — every `numpy.random`, `torch.manual_seed`, `sklearn random_state`, and data shuffling call. Forgetting one seed in a data splitting function produces irreproducible train/test splits.
4. **Feature engineering code versioned** — feature logic must live in a versioned Python module (not a notebook cell) with its git SHA logged to the MLflow run.

### 10.4 Jupyter Friction Points

**Git diffs on notebooks are broken.** Executed notebooks have embedded output cells, execution counts, and metadata changes that produce hundreds of lines of JSON diff for a one-line code change. Configure `nbstripout` as a git filter immediately and document it in this repo's CLAUDE.md.

**Notebooks are not testable.** Feature engineering code must eventually live in a `src/` package with unit tests. A function computing rolling kurtosis over a telemetry channel must be tested against known-good values with NaN gaps injected. No testing infrastructure exists currently for ML code.

**Restart-and-run-all is not sufficient for reproducibility.** Use Papermill for parameterized notebook execution via Dagster's `dagstermill` integration (notebooks become first-class assets) — this forces top-to-bottom execution with explicit parameters and produces a logged output notebook artifact in MLflow.

**Spark Connect latency on small queries.** Every `.show()`, `.describe()`, `.printSchema()` call incurs full gRPC round-trip, driver coordination, and result deserialization overhead — 8–15 seconds on this single-node cluster. Scientists compensate by sampling down to a local Pandas frame early and staying there. This is acceptable: Spark Connect is for scale-out, not exploration.

### 10.5 Model Selection for Spacecraft Anomaly Detection

**When labeled data is scarce (the default situation):**

- **Isolation Forest** — workhorse for tabular telemetry. Fast to train, interpretable (feature importance from isolation depth), handles high-dimensional feature spaces. Does not model temporal dependencies — must receive pre-computed temporal features as inputs.
- **LSTM Autoencoder** — appropriate when the temporal sequence itself carries the anomaly signal. High reconstruction error signals novelty. Sensitive to threshold selection; threshold drifts as the satellite ages. Requires careful window length selection.
- **Variational Autoencoder (VAE)** — probabilistic anomaly score (log-likelihood). More principled than reconstruction error. Enables uncertainty quantification, which operators need to assess alert confidence.

**When labeled anomaly windows exist:**

- **XGBoost / LightGBM** — most operationally mature, native NaN handling, fast training, built-in feature importance. Requires labeled data. Best starting point for supervised anomaly detection.
- **Temporal Fusion Transformer (TFT)** — state of the art for multi-variate time-series with attention weights showing which time steps and features drove the prediction. Interpretable for operator review. Significant compute requirement — GPU hardware not present on this local cluster.

**For single-channel trend monitoring:**

- **Prophet / SARIMA** — classical decomposition for detecting gross drift or seasonality violation. Interpretable without domain knowledge. Not ML but a critical component of a monitoring stack.

**Concept drift in spacecraft data.** Standard MLOps assumes drift is unexpected and bad. In spacecraft data, drift is often expected and physically caused: solar array degradation, radiation-induced dark current increase, reaction wheel bearing wear. A model must distinguish normal aging trends (retraining targets) from fault signatures (alert triggers). This requires domain-informed drift thresholds, not generic statistical tests.

**Explainability requirements.** Spacecraft operators must understand why a model flagged an anomaly before taking recovery action. Black-box scores are insufficient. SHAP values for tree models and attention weights for TFT provide the per-feature attribution that operators need to validate or dismiss an alert.

---

## 11. Critical Risk Analysis — Devil's Advocate

### 11.1 Complexity vs. Resource Reality

**The stack already exceeds its use cases.** The current platform runs eight distinct distributed systems on a single OrbStack node. The ML expansion proposes adding ~six more. Conservative RAM estimates at idle:

| Component | RAM (idle approx.) |
|-----------|-------------------|
| ArgoCD (server + repo-server + dex + redis + appcontroller) | ~800 MB |
| Strimzi operator + 1 Kafka broker | ~1.2 GB |
| Spark driver (idle) | ~512 MB |
| Iceberg REST server | ~256 MB |
| PostgreSQL | ~128 MB |
| MinIO | ~256 MB |
| JupyterLab | ~512 MB |
| **Current total (idle)** | **~3.7 GB** |
| A single Spark job, 2 executors | +2 GB |
| **ML additions** (MLflow, Feast, Redis, KServe, Dagster, Prometheus/Grafana/Loki, Marquez) | **+3–4 GB** |
| **Full expanded stack** | **~10–12 GB idle** |

A 16GB MacBook Pro running OrbStack, Docker, an IDE, and a browser will be at its practical limit before the ML expansion is complete. **32 GB unified memory is the realistic floor for the full proposed architecture.**

### 11.2 Technology Choices That Deserve Challenge

**Spark for ML.** Spark MLlib is not a serious contender for deep learning. It excels at large-scale feature engineering, batch scoring, and classical algorithms — not gradient-based training that dominates applied ML in 2025. The framing of "Spark for ML" should be replaced with "Spark for data engineering, PyTorch/scikit-learn for model development."

**Kafka + 300s microbatch.** This is batch processing with Kafka as the transport. Spark Structured Streaming's operational complexity (checkpointing, state management, watermarking) is fully present even though the latency profile is pure batch. At 300 seconds, consider whether simple Spark batch jobs on a cron schedule would be simpler to debug and restart on failure.

**Is Iceberg the right format for high-frequency telemetry?** Yes, for analytics workloads. No, for sub-second point lookups. The platform correctly keeps Iceberg as the analytical store and uses Redis for the hot path. Do not deviate from this.

**HBase at 0 replicas.** This is not neutral — it is worse than not having HBase. It occupies mental real estate in the architecture, ArgoCD watch loops, and namespace allocation. **Delete the HBase chart and ArgoCD application.** Redis serves the online feature store need with one-tenth the operational burden.

**Feature stores before features.** Feast is architecturally correct but premature. The training-serving skew problem Feast solves does not exist until a model is in production. Feature stores add Feast reconciliation, Redis, a registry database, and materialization jobs — significant ops cost for zero benefit before the first model deploys.

### 11.3 What Not to Build (Ordered by Priority to Skip)

1. **A feature store** — there is no training-serving skew problem yet. Build when two models need the same features and recomputing is genuinely painful.
2. **A/B testing infrastructure** — requires stable model serving first. It is the last mile, not the first.
3. **Drift detection** — meaningless before a model has a stable baseline. Add after the model has been in production for 30+ days.
4. **Distributed ML training (Ray/KubeRay)** — on a single physical node, this is complexity with no throughput benefit. Add when there is a multi-node cluster.
5. **Apicurio Schema Registry** — valuable long-term but not day-one critical for a simulator-driven pipeline where the producer is controlled.

### 11.4 Real vs. Synthetic Telemetry: Architectural Gap

The gap between a simulator and real spacecraft data is not just data volume — it is qualitative:

- **Binary CCSDS encoding** vs. JSON — real telemetry requires decommutation tooling not present in this platform
- **Clock drift and UTC reconstruction** vs. system timestamps correct by construction
- **Data gaps from contact pass schedules** vs. continuous Kafka ingestion
- **Multiple concurrent ground stations** producing duplicate packets vs. single producer
- **Hundreds of subsystem-specific parameters** with different cadences vs. a unified simplified schema

The current architecture is correctly scoped for the simulator. For real satellite integration, the ingestion layer requires a decommutation stage between the telemetry downlink and Kafka. This is a significant project on its own.

### 11.5 Space-Specific ML Concerns That the Architecture Cannot Resolve

- **Label scarcity is a domain problem, not an infrastructure problem.** No feature store, drift detector, or model registry changes the fact that a year of telemetry may contain 50,000 anomalous samples against 31 million nominal samples. The right response is domain-informed unsupervised methods, not more infrastructure.
- **Drift detection on spacecraft telemetry requires physics-informed baselines.** Generic PSI/KS tests will generate constant false alerts from orbital-phase-driven variation. This is a research problem, not an MLOps configuration problem.
- **Ground truth for anomaly labeling requires operator engagement.** Label Studio provides the UI, but the operational team must provide the labels. No automated system produces high-quality anomaly ground truth from spacecraft data.

### 10.6 Scientist's Prioritized Gap Assessment

Direct assessment of the current platform from a researcher's standpoint, ranked by daily workflow impact:

| Priority | Gap | Impact | Effort |
|----------|-----|--------|--------|
| 1 | No MLflow or experiment tracking | Cannot reproduce or compare experiments | Low — deploy on existing Postgres + MinIO |
| 2 | Iceberg REST catalog not externally accessible | Forced through Spark for all data access; add Traefik Ingress `iceberg.local` | Low — one Ingress rule |
| 3 | No Iceberg compaction job | Streaming table performance degrades within days | Low — Kubernetes CronJob |
| 4 | JupyterLab image not pinned or extended with ML libs | Environment drifts; `pyiceberg`, `duckdb`, `plotly`, `shap`, `scikit-learn` missing | Medium — custom Dockerfile layer |
| 5 | No data catalog or namespace convention | Onboarding friction; table discovery requires asking someone | Medium — documented conventions + a metadata table |
| 6 | No SHAP or explainability tooling | Operators cannot understand model alerts; won't act on them | Medium — add to Jupyter image, build explanation workflow |
| 7 | No commanded event log in telemetry schema | Cannot distinguish anomalies from commanded operations (safe mode, thruster firings) | High — simulator schema change |
| 8 | No low-latency feature store | Real-time scoring incurs MinIO roundtrip latency — not acceptable for online anomaly scoring | High — requires Redis |
| 9 | No drift detection or retraining pipeline | Production model becomes stale as sensors age, orbits precess, battery capacity declines | High — full MLOps pipeline |
| 10 | No multi-mission schema registry | Every new satellite mission is a greenfield integration exercise | Very High — architectural decision |

**Key platform access pattern** that should be enabled in Phase 1: expose the Iceberg REST catalog via a Traefik Ingress at `iceberg.local`, then scientists can query tables directly from JupyterLab without Spark using PyIceberg:
```
catalog = RestCatalog("local", uri="http://iceberg.local")
table = catalog.load_table("silver.telemetry_normalized")
df = table.scan(row_filter="event_timestamp > '2026-04-08'").to_pandas()
```
This enables the small-data exploratory workflow (Pandas + DuckDB + scikit-learn) without any Spark overhead.

---

## 12. Implementation Roadmap

Based on the devil's advocate's phased approach, validated against the architect's design and the scientist's workflow requirements.

### Phase 1 — Pipeline Integrity (Before Any ML)

**Goal:** a reliable, queryable Iceberg data lake with real (simulated) telemetry.

1. Verify end-to-end pipeline: simulator → Kafka → Spark SS → Iceberg bronze/silver
2. Reduce bronze microbatch from 300s → 60s
3. Deploy Dagster (`orchestration` namespace, Postgres backend) and implement the `iceberg_maintenance` asset job (compaction, expiry, orphan cleanup)
4. Add Prometheus + Grafana (kube-prometheus-stack) for pipeline observability
5. Delete HBase chart and ArgoCD application
6. Validate silver layer schema: `spacecraft_id, subsystem, metric_name, value, quality_flag, operational_mode, in_eclipse, event_timestamp`
7. Add rule-based anomaly detection (Tier 1 of the two-tier design)

**Deliverable:** stable, monitored, compacted Iceberg tables queryable from JupyterLab with sub-5s response for week-range queries.

### Phase 2 — First Model

**Goal:** one trained anomaly detection model, tracked, reproducible.

1. Deploy MLflow (backed by existing PostgreSQL and MinIO)
2. Train an Isolation Forest on gold layer features from JupyterLab (scikit-learn, not Spark MLlib)
3. Log training run to MLflow: snapshot IDs, hyperparameters, metrics, git SHA
4. Evaluate against a held-out labeled anomaly window (manually identified from simulator runs)
5. Register model in MLflow Model Registry (staging stage)

**Deliverable:** one registered model with a reproducible training run traceable to an Iceberg snapshot.

### Phase 3 — Simple Serving

**Goal:** the Phase 2 model is serving predictions. No A/B testing, no canary, no drift detection yet.

1. Deploy KServe (raw deployment mode, no Knative)
2. Serve the MLflow-registered model as a KServe `InferenceService`
3. Batch inference Dagster asset: nightly Spark job reads silver, loads model via `mlflow.pyfunc`, writes predictions to `ml.predictions`
4. Basic service health monitoring via Prometheus/Grafana

**Deliverable:** model predictions in Iceberg, observable via Grafana, triggered nightly by Dagster.

### Phase 4 — Operational Hardening (Demand-Driven)

Build components only when Phase 3 reveals concrete pain:

- **If training-serving skew is observed:** add Feast + Redis materialization
- **If multiple models need the same features:** add Feast feature registry
- **If model performance is degrading:** add Evidently drift monitoring
- **If manual retraining is painful:** add a Dagster ML training job with schedule/sensor triggers
- **If model promotion needs governance:** implement the git-based approval workflow (already designed in §5.1)
- **If exploration is slow:** add DuckDB + Polars to the JupyterLab image
- **If operator labeling is needed:** deploy Label Studio

---

## 13. Component Delta: What to Add vs. What Exists

### What Already Exists (Retain)

| Component | Role | Notes |
|-----------|------|-------|
| Apache Spark 3.5.3 (Spark Connect) | Batch + streaming compute | Reduce bronze microbatch to 60s |
| Iceberg REST Catalog (PostgreSQL backend) | Table metadata + time-travel | Never SQLite |
| MinIO | Object storage | Needs `mlflow-artifacts` and `telemetry-cold` buckets |
| PostgreSQL 16 | Catalog metadata | Add databases: `mlflow`, `dagster`, `feast_registry` |
| JupyterLab (pyspark-notebook) | Interactive analysis | Add DuckDB, Plotly, ydata-profiling, nbstripout |
| Kafka (Strimzi KRaft) | Event streaming | Add topics per §6.1 |
| Satellite Simulator | Telemetry source | Add `operational_mode` and `in_eclipse` fields |
| ArgoCD | GitOps control plane | No changes |

### What to Add (Phased)

| Component | Phase | Namespace | Justification |
|-----------|-------|-----------|--------------|
| Prometheus + Grafana + Alertmanager | 1 | `monitoring` | Pipeline observability baseline |
| Loki + Promtail | 1 | `monitoring` | Log aggregation |
| Dagster | 1 | `orchestration` | Asset-based orchestration; Iceberg maintenance, batch inference, drift, tiering |
| MLflow | 2 | `ml-platform` | Experiment tracking + model registry |
| KServe (raw mode) | 3 | `ml-serve` | Model serving CRD |
| Redis | 4 | `shared-services` | Online feature store (Feast dependency) |
| Feast | 4 | `ml-platform` | Feature store (only when skew is observed) |
| Evidently | 4 | `ml-platform` | Drift detection (only after stable model) |
| OpenLineage + Marquez | 4 | `ml-platform` | Data lineage (audit trail) |
| Great Expectations | 4 | `ml-platform` | Data quality gating |
| KubeRay | 5+ | `ml-train` | Only if deep learning requires multi-GPU |
| Label Studio | 4 | `ml-platform` | Operator anomaly labeling UI |
| Apicurio Schema Registry | 4 | `data-warehouse` | Schema enforcement for Kafka |

### What to Remove

| Component | Action | Reason |
|-----------|--------|--------|
| HBase (0 replicas) | **Delete Helm chart + ArgoCD Application** | Dead weight; use case covered by Redis when needed |

### What NOT to Build (Yet)

| Capability | Why to defer |
|-----------|-------------|
| Distributed training (Ray/KubeRay) | Single-node OrbStack cannot benefit; add at multi-node |
| A/B testing infrastructure | Requires stable serving first |
| Drift detection | Requires stable model baseline first (30+ days in production) |
| Feast feature store | Requires observed training-serving skew |
| Real CCSDS telemetry decommutation | Out of scope for simulator-based development |
| Multi-mission normalized schema | Future milestone, not day-one requirement |

---

*This document synthesizes outputs from three independent research agents: a principal data platform architect (Claude Opus), a devil's advocate engineer, and a space ML scientist. All three reviewed the existing OrbStack/ArgoCD platform and the proposed ML expansion.*
