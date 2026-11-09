"""Single place to build the SparkSession so config stays consistent."""
from pyspark.sql import SparkSession


def get_spark(app_name: str = "grocery-price-tracking") -> SparkSession:
    return (
        SparkSession.builder.appName(app_name)
        .master("local[*]")
        .config("spark.sql.shuffle.partitions", "4")  # small local default
        .config("spark.ui.showConsoleProgress", "false")
        .getOrCreate()
    )
