"""Shape Kroger product search results for the lake.

raw_products() is the Bronze step: keep every product the API returned, plus the
metadata needed to line snapshots up by store and day. egg_prices() is the Silver
step: flatten and filter to the egg products a report cares about. Bronze holds
every search term (eggs, milk, bread), so feed egg_prices only the rows whose
search_term is "eggs"; its description filter alone would let in e.g. "Egg Nog"
from the milk search.
"""

from datetime import date

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

# Match "egg" / "eggs" as whole words, so "eggplant" and "Eggo" are excluded.
EGG_PATTERN = r"\begg(s)?\b"


def raw_products(
    df: DataFrame,
    store_location_id: str,
    store_name: str,
    search_term: str,
    captured_date: date,
) -> DataFrame:
    """Add source metadata to the raw product search results, keeping every row.

    Bronze stores the API response as it came back, so the filters and price
    logic can change later without another API call.

    Arguments:
    df -- raw products from Kroger, with the fields the JSON API returned.
    store_location_id -- locationId of the store the prices came from.
    store_name -- human-readable store name.
    search_term -- term sent to the product search, e.g. "eggs" or "milk".
    captured_date -- day this snapshot belongs to. One snapshot per store, search
        term and day.

    Returns:
    the same products plus store, search and capture-date columns.
    """
    return df.select(
        F.lit(store_location_id).alias("store_location_id"),
        F.lit(store_name).alias("store_name"),
        F.lit(search_term).alias("search_term"),
        F.lit(captured_date).cast("date").alias("captured_date"),
        "*",
    )


def egg_prices(df: DataFrame, store_location_id: str, store_name: str) -> DataFrame:
    """Flatten Kroger product results into price observations for one store.

    Arguments:
    df -- raw products from the "eggs" search only, with productId, upc, brand,
        description, and items (a one-element array with size, price and
        inventory).
    store_location_id -- locationId of the store the prices came from.
    store_name -- human-readable store name.

    Returns:
    one row per egg product that has a price, sorted by effective price and
    description, with regular, promo and effective prices plus a capture time.
    """
    item = F.col("items")[0]
    price = item.getField("price")
    regular = price.getField("regular").cast("double")
    promo = price.getField("promo").cast("double")

    normalized = df.select(
        F.lit(store_location_id).alias("store_location_id"),
        F.lit(store_name).alias("store_name"),
        F.col("productId").alias("product_id"),
        F.col("upc"),
        F.col("brand"),
        F.col("description"),
        item.getField("size").alias("size"),
        regular.alias("regular_price"),
        promo.alias("promo_price"),
        F.when(promo > 0, promo).otherwise(regular).alias("effective_price"),
        item.getField("inventory").getField("stockLevel").alias("stock_level"),
        F.current_timestamp().alias("captured_at"),
    )

    return normalized.filter(
        F.col("description").isNotNull()
        & F.lower(F.col("description")).rlike(EGG_PATTERN)
        & F.col("effective_price").isNotNull()
    ).orderBy("effective_price", "description")
