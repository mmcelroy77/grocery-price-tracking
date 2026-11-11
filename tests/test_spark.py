import os

from pyspark.sql import SparkSession

from grocery_price_tracking.spark import _forward_stderr, get_spark


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
