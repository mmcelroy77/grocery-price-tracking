"""Single place to build the SparkSession so config stays consistent."""

import os
import threading
from pathlib import Path

from pyspark.sql import SparkSession

# Driver classpath entry for the project's log4j2.properties. This entry overrides Spark's
# bundled default config, which prints two "using default log4j" notices.
_LOG4J_DIR = Path(__file__).parent / "resources"

# Spark's launcher always passes --add-modules=jdk.incubator.vector, so the JVM prints
# the incubator notice on startup. No JVM flag turns off the notice, so stderr is filtered
# line by line.
_INCUBATOR_WARNING = b"WARNING: Using incubator modules"

_filtering = False


def _suppress_incubator_warning() -> None:
    original = os.dup(2)
    read_fd, write_fd = os.pipe()
    os.dup2(write_fd, 2)
    os.close(write_fd)

    def pump() -> None:
        with os.fdopen(read_fd, "rb", buffering=0) as stream:
            for line in stream:
                if _INCUBATOR_WARNING not in line:
                    os.write(original, line)

    threading.Thread(target=pump, daemon=True).start()


def configure(builder: SparkSession.Builder) -> SparkSession.Builder:
    """Apply project-wide logging config to any SparkSession builder."""
    global _filtering
    if not _filtering:
        _suppress_incubator_warning()
        _filtering = True
    # Local mode needs only loopback. Without this, Spark warns when the hostname resolves
    # to 127.0.1.1 (common on WSL) and binds to another address.
    os.environ.setdefault("SPARK_LOCAL_IP", "127.0.0.1")
    return builder.config("spark.driver.extraClassPath", str(_LOG4J_DIR))


def get_spark(app_name: str = "grocery-price-tracking") -> SparkSession:
    builder = (
        SparkSession.builder.appName(app_name)
        .master("local[*]")
        .config("spark.sql.shuffle.partitions", "4")  # small local default
        .config("spark.ui.showConsoleProgress", "false")
    )
    return configure(builder).getOrCreate()
