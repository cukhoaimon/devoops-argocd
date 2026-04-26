---
name: Orchestrator preference — Dagster, not Airflow
description: User dislikes Airflow; Dagster is the default orchestrator for this repo's data/ML platform
type: feedback
---

Default to **Dagster** (not Airflow) as the orchestrator when designing or updating data/ML pipelines in this repo. User explicitly rejected Airflow on 2026-04-09 after reviewing `docs/ml-platform-design.md`.

**Why:** User dislikes Airflow. Dagster is also a better architectural fit for this specific platform because its asset-oriented model maps 1:1 to the Iceberg lakehouse layers (bronze/silver/gold/features/ml), gives first-class partitioned-asset backfills for telemetry reprocessing, and emits OpenLineage natively — which reinforces the mission-critical provenance requirement already locked in.

**How to apply:**
- When proposing or editing orchestration in this repo, use Dagster terminology (assets, asset groups, ops, jobs, sensors, schedules, asset checks) — not Airflow DAGs/tasks/operators.
- Postgres backend lives in shared-services as database `dagster`.
- Use `dagster-ge` for Great Expectations integration, `dagstermill` for Papermill notebooks, `dagster-pyspark` for Spark, `dagster-openlineage` for lineage emission.
- User floated **Temporal** as an alternative — do not use Temporal for data orchestration. It is durable-execution for code workflows and lacks data/Spark/Iceberg/lineage primitives. Temporal remains on the table for future command-and-control or cross-system workflow problems (e.g., ground-station tasking, multi-system model promotion).
