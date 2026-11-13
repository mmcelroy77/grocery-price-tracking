import pytest
from botocore.exceptions import NoCredentialsError

from grocery_price_tracking.common import storage
from grocery_price_tracking.common.storage import (
    is_s3_path,
    lake_root,
    lake_uri,
    read_csv,
    read_delta,
    write_delta,
)


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("s3://bucket/key", True),
        ("s3a://bucket/key", True),
        ("data/raw/prices.csv", False),
        ("/tmp/s3a://nope", False),
    ],
)
def test_is_s3_path(path, expected):
    assert is_s3_path(path) is expected


def test_lake_root_defaults_to_project_bucket(monkeypatch):
    monkeypatch.delenv(storage.LAKE_ROOT_ENV)
    monkeypatch.setattr(storage, "get_account_id", lambda: "123456789012")
    assert lake_root() == "s3a://grocery-price-tracking-123456789012-data"


def test_lake_root_env_override(monkeypatch):
    monkeypatch.setenv(storage.LAKE_ROOT_ENV, "s3a://other-bucket/")
    assert lake_root() == "s3a://other-bucket"
    assert lake_uri("/silver/prices/") == "s3a://other-bucket/silver/prices"


def test_lake_root_explains_missing_credentials(monkeypatch):
    monkeypatch.delenv(storage.LAKE_ROOT_ENV)

    def no_credentials():
        raise NoCredentialsError

    monkeypatch.setattr(storage, "get_account_id", no_credentials)
    with pytest.raises(RuntimeError) as excinfo:
        lake_root()
    message = str(excinfo.value)
    assert "aws login" in message and "GROCERY_LAKE_ROOT=data/processed" in message


def test_read_csv_infers_types(spark, tmp_path):
    path = tmp_path / "prices.csv"
    path.write_text("item,price\nmilk,3.5\n")
    df = read_csv(spark, str(path))
    assert dict(df.dtypes) == {"item": "string", "price": "double"}


def test_write_delta_overwrite_round_trip(spark, tmp_path):
    uri = str(tmp_path / "t")
    first = write_delta(spark.createDataFrame([("milk", 1)], ["item", "qty"]), uri)
    # Overwrite with a different schema: replaces both rows and schema.
    df = spark.createDataFrame([("eggs", 2.0), ("milk", 3.0)], ["item", "price"])
    second = write_delta(df.coalesce(1), uri)

    result = read_delta(spark, uri)
    assert result.columns == ["item", "price"]
    assert [tuple(r) for r in result.orderBy("item").collect()] == [
        ("eggs", 2.0),
        ("milk", 3.0),
    ]
    assert (first.version, first.num_rows) == (0, 1)
    assert (second.version, second.num_rows) == (1, 2)
    assert second.num_files == 1
    parquet = list((tmp_path / "t").glob("*.parquet"))
    assert second.num_bytes == sum(f.stat().st_size for f in parquet) - (
        first.num_bytes
    )


def test_write_delta_append_partitioned(spark, tmp_path):
    uri = str(tmp_path / "t")
    schema = ["item", "store"]
    write_delta(
        spark.createDataFrame([("milk", "a")], schema), uri, partition_by=["store"]
    )
    stats = write_delta(
        spark.createDataFrame([("eggs", "b")], schema),
        uri,
        mode="append",
        partition_by=["store"],
    )

    rows = read_delta(spark, uri).orderBy("item").collect()
    assert [tuple(r) for r in rows] == [("eggs", "b"), ("milk", "a")]
    assert (stats.version, stats.num_rows, stats.num_files) == (1, 1, 1)
    assert (tmp_path / "t" / "store=a").is_dir()
