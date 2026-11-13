import pytest
from pyspark.sql import SparkSession

from grocery_price_tracking.common.storage import LAKE_ROOT_ENV
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


@pytest.fixture(autouse=True)
def lake_root(tmp_path, monkeypatch):
    """Keep every test's tables on local disk, never in the S3 bucket."""
    root = tmp_path / "lake"
    monkeypatch.setenv(LAKE_ROOT_ENV, str(root))
    return root
