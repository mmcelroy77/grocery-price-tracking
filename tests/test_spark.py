import os

from pyspark.sql import SparkSession

from grocery_price_tracking import spark as spark_module
from grocery_price_tracking.common.aws_auth import AwsCredentials
from grocery_price_tracking.common.storage import LAKE_REGION, LAKE_ROOT_ENV
from grocery_price_tracking.spark import (
    _forward_stderr,
    configure,
    get_spark,
    hadoop_version,
)


def test_forward_stderr_drops_only_the_incubator_warning():
    in_r, in_w = os.pipe()
    out_r, out_w = os.pipe()
    os.write(in_w, b"keep me\n")
    os.write(in_w, b"WARNING: Using incubator modules: jdk.incubator.vector\n")
    os.write(in_w, b"keep me too\n")
    os.close(in_w)

    _forward_stderr(in_r, out_w)
    os.close(out_w)

    with os.fdopen(out_r, "rb") as out:
        assert out.read() == b"keep me\nkeep me too\n"


def test_get_spark_returns_session(spark):
    # Reuses the session fixture's active session; don't stop it.
    assert isinstance(get_spark("tests"), SparkSession)


def test_hadoop_version_matches_bundled_jar():
    major, minor, _patch = hadoop_version().split(".")
    assert int(major) >= 3 and minor.isdigit()


def _conf(builder):
    return dict(builder._options)


def test_configure_enables_delta_without_s3():
    conf = _conf(configure(SparkSession.Builder()))

    assert conf["spark.sql.extensions"] == "io.delta.sql.DeltaSparkSessionExtension"
    assert "io.delta:delta-spark" in conf["spark.jars.packages"]
    assert "hadoop-aws" not in conf["spark.jars.packages"]


def test_configure_with_s3_adds_connector_and_settings():
    s3_conf = {"spark.hadoop.fs.s3a.access.key": "AKID"}
    conf = _conf(configure(SparkSession.Builder(), s3_conf=s3_conf))

    assert (
        f"org.apache.hadoop:hadoop-aws:{hadoop_version()}"
        in (conf["spark.jars.packages"])
    )
    assert conf["spark.hadoop.fs.s3a.access.key"] == "AKID"


def test_get_spark_adds_s3_conf_for_s3_lake(monkeypatch):
    monkeypatch.setenv(LAKE_ROOT_ENV, "s3a://bucket")
    monkeypatch.setattr(
        spark_module, "get_aws_credentials", lambda: AwsCredentials("AKID", "SECRET")
    )
    seen = {}

    def fake_configure(builder, *, s3_conf):
        seen.update(s3_conf)
        return builder

    monkeypatch.setattr(spark_module, "configure", fake_configure)
    get_spark("tests")  # returns the fixture's active session
    assert seen["spark.hadoop.fs.s3a.access.key"] == "AKID"
    assert seen["spark.hadoop.fs.s3a.endpoint.region"] == LAKE_REGION
