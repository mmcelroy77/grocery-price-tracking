"""Single place to build the SparkSession so config stays consistent."""

import os
import threading
from collections.abc import Mapping
from pathlib import Path

import pyspark
from delta import configure_spark_with_delta_pip
from pyspark.sql import SparkSession

from grocery_price_tracking.common.aws_auth import get_aws_credentials, s3a_spark_conf
from grocery_price_tracking.common.storage import LAKE_REGION, is_s3_path, lake_root

# Driver classpath entry for the project's log4j2.properties. This entry overrides Spark's
# bundled default config, which prints two "using default log4j" notices.
_LOG4J_DIR = Path(__file__).parent / "resources"

# Harmless JVM noise is dropped from stderr line by line:
# - Spark's launcher always passes --add-modules=jdk.incubator.vector, so the JVM
#   prints the incubator notice on startup. No JVM flag turns it off.
# - hadoop-aws still references the SLF4J 1.7 binder even though Spark 4 uses the
#   SLF4J 2 service loader (SPARK-52585). Spark's own log4j2 logging is unaffected.
_IGNORED_STDERR = (
    b"WARNING: Using incubator modules",
    b'SLF4J: Failed to load class "org.slf4j.impl.StaticLoggerBinder".',
    b"SLF4J: Defaulting to no-operation (NOP) logger implementation",
    b"SLF4J: See http://www.slf4j.org/codes.html#StaticLoggerBinder",
    b"SLF4J: See https://www.slf4j.org/codes.html#StaticLoggerBinder",
)

_filtering = False

# Parquet's MemoryManager checks every live writer's row group against the heap and
# shrinks row groups past 95% of it. A local[*] session runs one writer per core and
# each reserves a full row group (128 MB), so the 1 GiB default already trips at 9
# writers. Two gigabytes fits 12 writers; raise it on machines with more cores.
DRIVER_MEMORY_ENV = "SPARK_DRIVER_MEMORY"
DEFAULT_DRIVER_MEMORY = "2g"

_DELTA_CONF = {
    "spark.sql.extensions": "io.delta.sql.DeltaSparkSessionExtension",
    "spark.sql.catalog.spark_catalog": (
        "org.apache.spark.sql.delta.catalog.DeltaCatalog"
    ),
}


def _forward_stderr(read_fd: int, out_fd: int) -> None:
    """Copy lines from one file descriptor to another, dropping known JVM noise.

    Runs until read_fd reaches EOF, then closes it.

    Arguments:
    read_fd -- file descriptor to read lines from (the read end of the stderr pipe).
    out_fd -- file descriptor to write kept lines to (the original stderr).
    """
    with os.fdopen(read_fd, "rb", buffering=0) as stream:
        for line in stream:
            if not any(marker in line for marker in _IGNORED_STDERR):
                os.write(out_fd, line)


def _suppress_stderr_noise() -> None:
    """Route stderr through a filter that drops harmless JVM warnings.

    Replaces file descriptor 2 with a pipe and starts a daemon thread that forwards
    every other line to the original stderr. Call at most once per process.
    """
    original = os.dup(2)
    read_fd, write_fd = os.pipe()
    os.dup2(write_fd, 2)
    os.close(write_fd)
    threading.Thread(
        target=_forward_stderr, args=(read_fd, original), daemon=True
    ).start()


def hadoop_version() -> str:
    """Return the Hadoop version bundled with pyspark.

    hadoop-aws must match this version exactly, so it is read from the installed
    jars instead of being pinned separately.

    Returns:
    the version string, e.g. "3.4.2".

    Raises:
    StopIteration -- if pyspark ships no hadoop-client-api jar.
    """
    jars = Path(pyspark.__file__).parent / "jars"
    jar = next(jars.glob("hadoop-client-api-*.jar"))
    return jar.stem.removeprefix("hadoop-client-api-")


def driver_memory() -> str:
    """Return the driver heap to request when the session starts.

    Returns:
    SPARK_DRIVER_MEMORY if set, otherwise DEFAULT_DRIVER_MEMORY, e.g. "2g".
    """
    return os.environ.get(DRIVER_MEMORY_ENV, DEFAULT_DRIVER_MEMORY)


def configure(
    builder: SparkSession.Builder, *, s3_conf: Mapping[str, str] | None = None
) -> SparkSession.Builder:
    """Apply project-wide config to any SparkSession builder.

    Always sets up logging and enables Delta Lake. Jars are downloaded from Maven on
    first use and cached in ~/.ivy2.5.2; the AWS SDK bundle that hadoop-aws needs is
    large.

    Arguments:
    builder -- the builder to configure. Settings already on it are kept unless
        this function overrides them.
    s3_conf -- S3A settings from common.aws_auth.s3a_spark_conf(); when given,
        the S3A connector is added too, so s3:// and s3a:// paths work.

    Returns:
    the configured builder; call getOrCreate() on it.
    """
    global _filtering
    if not _filtering:
        _suppress_stderr_noise()
        _filtering = True
    # Local mode needs only loopback. Without this, Spark warns when the hostname resolves
    # to 127.0.1.1 (common on WSL) and binds to another address.
    os.environ.setdefault("SPARK_LOCAL_IP", "127.0.0.1")
    builder = builder.config("spark.driver.extraClassPath", str(_LOG4J_DIR))
    builder = builder.config("spark.driver.memory", driver_memory())
    builder = builder.config(map=_DELTA_CONF)
    extra_packages = []
    if s3_conf:
        builder = builder.config(map=dict(s3_conf))
        extra_packages = [f"org.apache.hadoop:hadoop-aws:{hadoop_version()}"]
    return configure_spark_with_delta_pip(builder, extra_packages=extra_packages)


def get_spark(app_name: str = "grocery-price-tracking") -> SparkSession:
    """Create (or reuse) the local SparkSession for a job.

    Adds S3 access when the lake root (see common.storage) is in S3.

    Arguments:
    app_name -- name shown in the Spark UI and logs.

    Returns:
    the active SparkSession. If one already exists, it is returned as is.

    Raises:
    RuntimeError -- if storage is in S3 and no AWS credentials can be found.
    """
    builder = (
        SparkSession.builder.appName(app_name)
        .master("local[*]")
        .config("spark.sql.shuffle.partitions", "4")  # small local default
        .config("spark.ui.showConsoleProgress", "false")
    )
    s3_conf = None
    if is_s3_path(lake_root()):
        s3_conf = s3a_spark_conf(get_aws_credentials(), LAKE_REGION)
    return configure(builder, s3_conf=s3_conf).getOrCreate()
