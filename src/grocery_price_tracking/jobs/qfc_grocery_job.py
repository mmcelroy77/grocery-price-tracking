"""Entry point: snapshot grocery search results from one QFC store near ZIP 98012.

The Kroger public API needs a free developer app. Set KROGER_CLIENT_ID and
KROGER_CLIENT_SECRET before running. The store is resolved at runtime as the
nearest QFC (or KROGER_CHAIN) to KROGER_STORE_ZIP, so a closed store does not
break the job.

Rows land in the Bronze table, unfiltered and grouped by day: one snapshot per
store, search term and captured_date. Re-running on the same day replaces that
day's snapshot instead of appending a duplicate.

A snapshot is all or nothing: if any search term returns no products, nothing is
written for the day, so Bronze never holds a partial day.
"""

import json
import os
from datetime import date

from grocery_price_tracking.common.kroger import (
    credentials_from_env,
    find_store,
    get_access_token,
    load_dotenv,
    search_products,
)
from grocery_price_tracking.common.storage import WriteStats, lake_uri, write_delta
from grocery_price_tracking.spark import get_spark
from grocery_price_tracking.transforms.kroger import raw_products

DEFAULT_ZIP = "98012"
DEFAULT_CHAIN = "QFC"
SEARCH_TERMS = ["eggs", "milk", "bread"]
OUTPUT = "bronze/kroger/products"
DATE_COLUMN = "captured_date"


def run() -> WriteStats:
    """Snapshot one store's product search results for today into Bronze.

    Prints the store, the products and the write stats. Stops the SparkSession
    when done. The Dagster asset (see orchestration.definitions) calls this too.

    Returns:
    the stats of the Bronze write.

    Raises:
    KrogerError -- if the Kroger credentials are missing or the API cannot be used.
    RuntimeError -- if any search term returns no products.
    """
    load_dotenv()
    client_id, client_secret = credentials_from_env()
    token = get_access_token(client_id, client_secret)
    zip_code = os.environ.get("KROGER_STORE_ZIP", DEFAULT_ZIP)
    chain = os.environ.get("KROGER_CHAIN", DEFAULT_CHAIN)
    store = find_store(token, zip_code, chain)
    location_id = store["locationId"]
    store_name = store["name"]
    captured_date = date.today()
    spark = get_spark("qfc-grocery-job")
    try:
        json_by_term = {}
        for term in SEARCH_TERMS:
            term_products = search_products(token, term, location_id)
            if not term_products:
                raise RuntimeError(
                    f"Kroger returned no {term} products for {store_name}."
                )
            json_by_term[term] = [json.dumps(p) for p in term_products]
        total_products = sum(len(rows) for rows in json_by_term.values())
        # Infer one schema from every term's products, so a field that differs
        # between searches can't make the terms impossible to combine.
        schema = spark.read.json(
            spark.sparkContext.parallelize(
                [row for rows in json_by_term.values() for row in rows]
            )
        ).schema
        products_by_term = [
            raw_products(
                spark.read.schema(schema).json(spark.sparkContext.parallelize(rows)),
                location_id,
                store_name,
                term,
                captured_date,
            )
            for term, rows in json_by_term.items()
        ]
        bronze = products_by_term[0]
        for df_term in products_by_term[1:]:
            bronze = bronze.unionByName(df_term)
        print(
            f"{store_name} ({location_id}) near {zip_code}: {', '.join(SEARCH_TERMS)}"
        )
        print(f"{total_products} products captured for {captured_date}")
        uri = lake_uri(OUTPUT)
        stats = write_delta(
            bronze,
            uri,
            partition_by=[DATE_COLUMN],
            replace_where=f"{DATE_COLUMN} = DATE '{captured_date.isoformat()}'",
            merge_schema=True,
        )
        print(
            f"Wrote {stats.num_rows} rows ({stats.num_bytes:,} bytes, "
            f"{stats.num_files} files) to {uri} as version {stats.version}"
        )
        return stats
    finally:
        spark.stop()


def main() -> None:
    """Run the job from the command line (the gpt-grocery script)."""
    run()


if __name__ == "__main__":
    main()
