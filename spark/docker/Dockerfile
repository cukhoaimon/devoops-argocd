FROM apache/spark:3.5.3-python3

USER root

ENV ICEBERG_VERSION=1.6.1
ENV SPARK_VERSION=3.5
ENV SPARK_FULL_VERSION=3.5.3
ENV SCALA_VERSION=2.12

# Spark Connect jar (not included in base image)
ADD https://repo1.maven.org/maven2/org/apache/spark/spark-connect_${SCALA_VERSION}/${SPARK_FULL_VERSION}/spark-connect_${SCALA_VERSION}-${SPARK_FULL_VERSION}.jar \
    /opt/spark/jars/

# Iceberg runtime (bao gồm cả Spark extensions)
ADD https://repo1.maven.org/maven2/org/apache/iceberg/iceberg-spark-runtime-${SPARK_VERSION}_${SCALA_VERSION}/${ICEBERG_VERSION}/iceberg-spark-runtime-${SPARK_VERSION}_${SCALA_VERSION}-${ICEBERG_VERSION}.jar \
    /opt/spark/jars/

# AWS SDK bundle (để Spark đọc S3/MinIO)
ADD https://repo1.maven.org/maven2/software/amazon/awssdk/bundle/2.20.18/bundle-2.20.18.jar \
    /opt/spark/jars/

# URL connection factory (bắt buộc khi dùng REST catalog)
ADD https://repo1.maven.org/maven2/org/apache/iceberg/iceberg-aws-bundle/${ICEBERG_VERSION}/iceberg-aws-bundle-${ICEBERG_VERSION}.jar \
    /opt/spark/jars/

# Python packages
RUN pip install --no-cache-dir \
    pyspark==3.5.3 \
    pyiceberg==0.7.1 \
    pandas==2.0.2 \
    pyarrow==17.0.0

USER 185