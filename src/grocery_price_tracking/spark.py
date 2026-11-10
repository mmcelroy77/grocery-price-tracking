"""Single place to build the SparkSession so config stays consistent."""

from pyspark.sql import SparkSession


def get_spark(app_name: str = "grocery-price-tracking") -> SparkSession:
    # Spark's launcher always adds --add-modules=jdk.incubator.vector, so the JVM prints
    # "WARNING: Using incubator modules: jdk.incubator.vector" on startup. It's expected and harmless.
    return (
        SparkSession.builder.appName(app_name)
        .master("local[*]")
        .config("spark.sql.shuffle.partitions", "4")  # small local default
        .config("spark.ui.showConsoleProgress", "false")
        .getOrCreate()
    )