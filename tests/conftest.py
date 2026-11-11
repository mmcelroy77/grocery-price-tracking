import pytest
from pyspark.sql import SparkSession

from grocery_price_tracking.spark import configure


@pytest.fixture(scope="session")
def spark():
    builder = (
        SparkSession.builder.master("local[1]")
        .appName("tests")
        .config("spark.sql.shuffle.partitions", "1")
    )
    session = configure(builder).getOrCreate()
    yield session
    session.stop()
