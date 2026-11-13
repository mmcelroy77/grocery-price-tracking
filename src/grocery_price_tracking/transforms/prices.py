"""Pure DataFrame -> DataFrame transforms. No I/O here, so they're easy to test."""

from pyspark.sql import DataFrame
from pyspark.sql import functions as F


def avg_price_by_item(df: DataFrame) -> DataFrame:
    """Summarize prices per item.

    Arguments:
    df -- price observations with at least "item" and "price" columns.

    Returns:
    one row per item, sorted by item, with columns item, avg_price (rounded to
    2 decimals), min_price and max_price.
    """
    return (
        df.groupBy("item")
        .agg(
            F.round(F.avg("price"), 2).alias("avg_price"),
            F.min("price").alias("min_price"),
            F.max("price").alias("max_price"),
        )
        .orderBy("item")
    )
