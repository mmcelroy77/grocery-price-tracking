"""Entry point: read raw CSV, transform, print. Jobs own I/O; transforms own logic."""

import argparse

from grocery_price_tracking.spark import get_spark
from grocery_price_tracking.transforms.prices import avg_price_by_item


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/raw/prices.csv")
    args = parser.parse_args()

    spark = get_spark("sample-job")
    try:
        df = spark.read.csv(args.input, header=True, inferSchema=True)
        avg_price_by_item(df).show()
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
