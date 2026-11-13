"""File operations for jobs.

Read/write functions take a full URI. Jobs build it with lake_uri("sample/prices")
so they don't need to know where storage lives. The root is the project's S3 data
bucket (derived from the AWS account, matching infra/main.tf), or GROCERY_LAKE_ROOT if
set, e.g. GROCERY_LAKE_ROOT=data/processed to keep everything on local disk.
"""

import os
from collections.abc import Sequence
from dataclasses import dataclass

from delta.tables import DeltaTable
from pyspark.sql import DataFrame, SparkSession

from grocery_price_tracking.common.aws_auth import get_account_id

LAKE_ROOT_ENV = "GROCERY_LAKE_ROOT"
# Must match var.project and var.region in infra/variables.tf.
PROJECT = "grocery-price-tracking"
LAKE_REGION = "us-east-2"
S3_SCHEMES = ("s3://", "s3a://")


def is_s3_path(path: str) -> bool:
    """Check whether a path is an S3 URI.

    Arguments:
    path -- a local path or URI.

    Returns:
    True if path starts with s3:// or s3a://.
    """
    return path.startswith(S3_SCHEMES)


def lake_root() -> str:
    """Return where tables live.

    Returns:
    GROCERY_LAKE_ROOT without a trailing slash if set, otherwise the project's S3
    data bucket, e.g. "s3a://grocery-price-tracking-<account id>-data".

    Raises:
    botocore.exceptions.NoCredentialsError -- if GROCERY_LAKE_ROOT is unset and
        no AWS credentials are configured.
    """
    override = os.environ.get(LAKE_ROOT_ENV)
    if override:
        return override.rstrip("/")
    return f"s3a://{PROJECT}-{get_account_id()}-data"


def lake_uri(path: str) -> str:
    """Build the full URI for a path under the lake root.

    Arguments:
    path -- path relative to the lake root, e.g. "sample/avg_price_by_item".
        Leading and trailing slashes are ignored.

    Returns:
    the full URI, e.g. "s3a://<bucket>/sample/avg_price_by_item".
    """
    return f"{lake_root()}/{path.strip('/')}"


def read_csv(spark: SparkSession, path: str) -> DataFrame:
    """Read a CSV file that has a header row.

    Arguments:
    spark -- active SparkSession.
    path -- local path or URI of the file (or directory of files).

    Returns:
    the file's rows as a DataFrame, with column types inferred.
    """
    return spark.read.options(header="true", inferSchema="true").csv(path)


def read_delta(spark: SparkSession, uri: str) -> DataFrame:
    """Read the latest version of a Delta table.

    Arguments:
    spark -- active SparkSession with Delta enabled (see spark.configure).
    uri -- table location, e.g. from lake_uri().

    Returns:
    the table's rows as a DataFrame.
    """
    return spark.read.format("delta").load(uri)


@dataclass(frozen=True)
class WriteStats:
    """What one write added, from the Delta commit (no extra scan of the data).

    Attributes:
    version -- table version the write created.
    num_rows -- rows written.
    num_bytes -- bytes of data files written.
    num_files -- data files written.
    """

    version: int
    num_rows: int
    num_bytes: int
    num_files: int


def write_delta(
    df: DataFrame,
    uri: str,
    *,
    mode: str = "overwrite",
    partition_by: Sequence[str] = (),
) -> WriteStats:
    """Write a DataFrame as a Delta table and return what the write added.

    Stats come from the latest commit, so they assume one writer per table.

    Arguments:
    df -- rows to write.
    uri -- table location, e.g. from lake_uri(). Created if missing.
    mode -- "overwrite" replaces the data and schema (history is kept);
        "append" adds rows and rejects schema changes.
    partition_by -- columns to partition the table by. Empty for none.

    Returns:
    row, byte and file counts for this write, and the new table version.
    """
    writer = df.write.format("delta").mode(mode)
    if mode == "overwrite":
        writer = writer.option("overwriteSchema", "true")
    if partition_by:
        writer = writer.partitionBy(*partition_by)
    writer.save(uri)

    commit = DeltaTable.forPath(df.sparkSession, uri).history(1).first()
    metrics = commit.operationMetrics
    return WriteStats(
        version=commit.version,
        num_rows=int(metrics["numOutputRows"]),
        num_bytes=int(metrics["numOutputBytes"]),
        num_files=int(metrics["numFiles"]),
    )
