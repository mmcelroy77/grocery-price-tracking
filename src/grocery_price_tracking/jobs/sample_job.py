"""Entry point: read raw CSV, transform, write Delta. Jobs own I/O; transforms own logic.

Output goes under the lake root (see common.storage): the S3 data bucket by
default, or GROCERY_LAKE_ROOT if set.
"""

from grocery_price_tracking.common.storage import (
    lake_uri,
    read_csv,
    read_delta,
    write_delta,
)
from grocery_price_tracking.spark import get_spark
from grocery_price_tracking.transforms.prices import avg_price_by_item

INPUT = "data/raw/prices.csv"
OUTPUT = "sample/avg_price_by_item"


def main() -> None:
    """Average the sample prices and write them as a Delta table under OUTPUT.

    Prints the result and the write stats. Stops the SparkSession when done.
    """
    spark = get_spark("sample-job")
    try:
        result = avg_price_by_item(read_csv(spark, INPUT))
        uri = lake_uri(OUTPUT)
        stats = write_delta(result, uri)
        # Show the written table: cheaper than recomputing result from the CSV.
        read_delta(spark, uri).orderBy("item").show()
        print(
            f"Wrote {stats.num_rows} rows ({stats.num_bytes:,} bytes, "
            f"{stats.num_files} files) to {uri} as version {stats.version}"
        )
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
