FROM apache/spark:3.5.3-python3

USER root

ENV ICEBERG_VERSION=1.6.1
ENV SPARK_VERSION=3.5
ENV SPARK_FULL_VERSION=3.5.3
ENV SCALA_VERSION=2.12

# Download all JARs and fix permissions in one layer.
# RUN wget is used instead of ADD <url> because:
#   - All 8 downloads + chmod collapse into a single image layer
#   - This layer is properly cached when the ENV vars above don't change
#   - ADD <url> never uses Docker's build cache (always re-downloads)
RUN MAVEN="https://repo1.maven.org/maven2" && \
    wget -q -P /opt/spark/jars/ \
        "${MAVEN}/org/apache/spark/spark-connect_${SCALA_VERSION}/${SPARK_FULL_VERSION}/spark-connect_${SCALA_VERSION}-${SPARK_FULL_VERSION}.jar" \
        "${MAVEN}/org/apache/iceberg/iceberg-spark-runtime-${SPARK_VERSION}_${SCALA_VERSION}/${ICEBERG_VERSION}/iceberg-spark-runtime-${SPARK_VERSION}_${SCALA_VERSION}-${ICEBERG_VERSION}.jar" \
        "${MAVEN}/software/amazon/awssdk/bundle/2.20.18/bundle-2.20.18.jar" \
        "${MAVEN}/org/apache/iceberg/iceberg-aws-bundle/${ICEBERG_VERSION}/iceberg-aws-bundle-${ICEBERG_VERSION}.jar" \
        "${MAVEN}/org/apache/spark/spark-sql-kafka-0-10_${SCALA_VERSION}/${SPARK_FULL_VERSION}/spark-sql-kafka-0-10_${SCALA_VERSION}-${SPARK_FULL_VERSION}.jar" \
        "${MAVEN}/org/apache/spark/spark-token-provider-kafka-0-10_${SCALA_VERSION}/${SPARK_FULL_VERSION}/spark-token-provider-kafka-0-10_${SCALA_VERSION}-${SPARK_FULL_VERSION}.jar" \
        "${MAVEN}/org/apache/kafka/kafka-clients/3.4.1/kafka-clients-3.4.1.jar" \
        "${MAVEN}/org/apache/commons/commons-pool2/2.12.0/commons-pool2-2.12.0.jar" && \
    chmod 644 /opt/spark/jars/*.jar

# Python packages
RUN pip install --no-cache-dir \
    pyspark==3.5.3 \
    pyiceberg==0.7.1 \
    pandas==2.0.2 \
    pyarrow==17.0.0

USER 185
