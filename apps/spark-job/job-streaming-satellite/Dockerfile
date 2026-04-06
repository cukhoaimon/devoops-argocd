# ─── Satellite Telemetry Stream ───────────────────────────────────────────────
# Reuses the same custom Spark image as the cluster's Spark Connect server.
# That image already ships all required JARs:
#   • spark-sql-kafka-0-10  (Kafka source)
#   • kafka-clients + commons-pool2
#   • iceberg-spark-runtime (Iceberg catalog + table format)
#   • iceberg-aws-bundle + aws-sdk-bundle (S3FileIO → MinIO)
# No extra --packages or wget needed here.
# ─────────────────────────────────────────────────────────────────────────────

FROM ghcr.io/cukhoaimon/spark-iceberg:3.5.3

USER root

WORKDIR /opt/spark/work-dir

# Copy application source
COPY stream/ ./stream/
COPY main.py  ./main.py

# Fix ownership so the non-root spark user (UID 185) can read the files
RUN chown -R 185:185 /opt/spark/work-dir

USER 185

# spark-submit runs in local[*] mode by default.
# Override SPARK_MASTER env var to point at a different master
# (e.g. k8s://https://kubernetes.default.svc) when deploying via K8s.
ENTRYPOINT ["/opt/spark/bin/spark-submit", \
            "--master", "local[*]", \
            "--deploy-mode", "client", \
            "/opt/spark/work-dir/main.py"]
