FROM apache/spark:4.0.0-python3

USER root

ENV ICEBERG_VERSION=1.10.1
ENV SPARK_VERSION=4.0
ENV SPARK_FULL_VERSION=4.0.0
ENV SCALA_VERSION=2.13
ENV HADOOP_VERSION=3.4.1

# Download all JARs and fix permissions in one layer.
# RUN wget is used instead of ADD <url> because:
#   - All downloads + chmod collapse into a single image layer
#   - This layer is properly cached when the ENV vars above don't change
#   - ADD <url> never uses Docker's build cache (always re-downloads)
#
# Spark 4.0 changes vs 3.5:
#   - Scala 2.13 only (all _2.12 coordinates become _2.13)
#   - hadoop-aws upgraded to 3.4.1 (AWS SDK v2; SDK v1 support dropped)
#   - AWS SDK v1 JARs removed (sdk-s3/core/sts) — SDK v2 provided by iceberg-aws-bundle
#   - Iceberg upgraded to 1.8.1 (first stable series with Spark 4.0 runtime)
RUN MAVEN="https://repo1.maven.org/maven2" && \
    wget -q -P /opt/spark/jars/ \
        "${MAVEN}/org/apache/spark/spark-connect_${SCALA_VERSION}/${SPARK_FULL_VERSION}/spark-connect_${SCALA_VERSION}-${SPARK_FULL_VERSION}.jar" \
        "${MAVEN}/org/apache/iceberg/iceberg-spark-runtime-${SPARK_VERSION}_${SCALA_VERSION}/${ICEBERG_VERSION}/iceberg-spark-runtime-${SPARK_VERSION}_${SCALA_VERSION}-${ICEBERG_VERSION}.jar" \
        "${MAVEN}/org/apache/iceberg/iceberg-aws-bundle/${ICEBERG_VERSION}/iceberg-aws-bundle-${ICEBERG_VERSION}.jar" \
        "${MAVEN}/org/apache/hadoop/hadoop-aws/${HADOOP_VERSION}/hadoop-aws-${HADOOP_VERSION}.jar" \
        "${MAVEN}/org/apache/spark/spark-sql-kafka-0-10_${SCALA_VERSION}/${SPARK_FULL_VERSION}/spark-sql-kafka-0-10_${SCALA_VERSION}-${SPARK_FULL_VERSION}.jar" \
        "${MAVEN}/org/apache/spark/spark-token-provider-kafka-0-10_${SCALA_VERSION}/${SPARK_FULL_VERSION}/spark-token-provider-kafka-0-10_${SCALA_VERSION}-${SPARK_FULL_VERSION}.jar" \
        "${MAVEN}/org/apache/kafka/kafka-clients/3.7.0/kafka-clients-3.7.0.jar" \
        "${MAVEN}/org/apache/commons/commons-pool2/2.12.0/commons-pool2-2.12.0.jar" \
        "${MAVEN}/software/amazon/awssdk/s3-transfer-manager/2.33.0/s3-transfer-manager-2.33.0.jar" && \
    chmod 644 /opt/spark/jars/*.jar

# Python packages
RUN pip install --no-cache-dir \
    pyiceberg==0.11.1 \
    pandas==2.2.3 \
    pyarrow==17.0.0

USER 185
