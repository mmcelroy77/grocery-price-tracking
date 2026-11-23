"""Dagster definitions for the project.

Run the UI locally with `dagster dev`, or run one asset without it:
`dagster asset materialize -m grocery_price_tracking.orchestration.definitions
--select kroger_bronze_products`. The module is registered in pyproject.toml under
[tool.dagster].
"""

from dagster import Backoff, Definitions, MaterializeResult, RetryPolicy, asset

from grocery_price_tracking.common.storage import lake_uri
from grocery_price_tracking.jobs import qfc_eggs_job

# The Kroger API can fail transiently, so retry twice (after 1 and 2 minutes). Errors
# that can't fix themselves, like missing credentials, retry too, which only delays
# the failure by about three minutes.
RETRY_POLICY = RetryPolicy(max_retries=2, delay=60, backoff=Backoff.EXPONENTIAL)


@asset(
    group_name="bronze",
    retry_policy=RETRY_POLICY,
    description="Today's QFC egg-search snapshot from the Kroger API (Bronze Delta).",
)
def kroger_bronze_products() -> MaterializeResult:
    """Snapshot today's Kroger egg search into the Bronze Delta table.

    Returns:
    the write stats as asset metadata: table location, version, rows, bytes, files.
    """
    stats = qfc_eggs_job.run()
    uri = lake_uri(qfc_eggs_job.OUTPUT)
    return MaterializeResult(
        metadata={
            "uri": uri,
            "delta_version": stats.version,
            "num_rows": stats.num_rows,
            "num_bytes": stats.num_bytes,
            "num_files": stats.num_files,
        }
    )


defs = Definitions(assets=[kroger_bronze_products])
