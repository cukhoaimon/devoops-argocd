from pyspark.sql import SparkSession

spark = SparkSession.builder.appName("job-general").getOrCreate()

# Catalog & S3 config is already loaded from spark-defaults ConfigMap
spark.sql("SELECT * FROM climate.weather").show()

spark.stop()
