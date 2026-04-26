---
name: ML Platform Architecture Review (2026-04-08)
description: Open issues from review of user's satellite-telemetry data+ML platform diagram (Kafka→Spark→Iceberg→Ray/MLflow)
type: project
---

User shared an architecture diagram for a satellite-telemetry data + ML platform built on the existing repo stack (Strimzi Kafka, Spark Structured Streaming, Iceberg REST, MinIO medallion, Temporal, Ray, MLflow, Cassandra online feature store). Review surfaced these open issues, in priority order:

1. **Catalog SPOF (blocker):** Diagram shows Iceberg REST → Postgres, but repo's iceberg chart still uses SQLite on PVC. Single-writer, will corrupt under concurrent writers. Migrate to Postgres (CloudNativePG).
2. **No Schema Registry** between satellite-simulator and Kafka topic `satellite-telemetry`. Add Apicurio/Confluent + Avro/Protobuf.
3. **Streaming checkpoints** durability not specified — must be `s3a://` on MinIO, not pod ephemeral.
4. **Feature store skew risk:** Cassandra online store drawn but no Feast offline store link or materialization workflow. Wire Feast with Iceberg Gold offline + Cassandra online, materialized by Temporal.
5. **Model promotion gate missing:** Ray train → MLflow → Ray Serve has no eval gate or registry stage transition. Add Temporal workflow: train → log → eval → promote → rolling deploy.
6. **Monitoring gap:** Grafana floating; no model drift signals. Add Evidently/Whylogs → Prometheus alongside infra + pipeline metrics (Kafka Exporter, Spark listener, Iceberg commits).
7. **No data quality stage** Bronze→Silver. Add Great Expectations / Soda, fail Temporal workflow on violation.
8. **Image tagging:** two duplicate `ghcr/cukhoaimon/spark-job:latest` boxes; `:latest` breaks reproducibility — pin by digest/git SHA.
9. **Lineage:** Add OpenLineage emitters (Spark + Temporal) → Marquez for telemetry provenance (matters for space/ITAR contexts).
10. **Minor:** "Sliver" typo → "Silver" (×3); clarify JupyterHub auth path through Traefik (drawn in Outbound but pod is in-cluster).

**Why:** User asked "is this good to go" — verdict was not ship-ready but ~2 iterations away. Priorities 1–5 are the must-fix set.

**How to apply:** When the user returns to this work, check whether these have been addressed (especially #1 Postgres catalog migration in `iceberg/` chart). User was offered next-step drafts for (a) the Temporal train→gate→promote→deploy workflow, or (b) Postgres-backed Iceberg REST Helm values — pick up there.

Diagram source: `docs/architecture-lm.md` and/or `docs/ml-architecture.md` (untracked at time of review).
