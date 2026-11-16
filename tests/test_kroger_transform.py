import json
from datetime import date

from grocery_price_tracking.transforms.kroger import egg_prices, raw_products

PRODUCTS = [
    {
        "productId": "0001111060903",
        "upc": "0001111060903",
        "brand": "Simple Truth",
        "description": "Large Brown Eggs, 12 ct",
        "items": [
            {
                "size": "12 ct",
                "price": {"regular": 5.99, "promo": 0},
                "inventory": {"stockLevel": "HIGH"},
            }
        ],
    },
    {
        "productId": "0001111060904",
        "upc": "0001111060904",
        "brand": "Kroger",
        "description": "Egg Whites, 16 oz",
        "items": [
            {
                "size": "16 oz",
                "price": {"regular": 4.49, "promo": 3.99},
                "inventory": {"stockLevel": "LOW"},
            }
        ],
    },
    {
        "productId": "0001111060905",
        "upc": "0001111060905",
        "brand": "Produce",
        "description": "Eggplant",
        "items": [
            {
                "size": "1 ct",
                "price": {"regular": 2.99, "promo": 0},
                "inventory": {"stockLevel": "HIGH"},
            }
        ],
    },
    {
        "productId": "0001111060906",
        "upc": "0001111060906",
        "brand": "Kellogg's",
        "description": "Eggo Waffles",
        "items": [
            {
                "size": "10 ct",
                "price": {"regular": 3.49, "promo": 0},
                "inventory": {"stockLevel": "HIGH"},
            }
        ],
    },
    {
        "productId": "0001111060907",
        "upc": "0001111060907",
        "brand": "Kroger",
        "description": "Eggs, no price",
        "items": [{"size": "12 ct", "price": {"regular": None, "promo": 0}}],
    },
]


def read_products(spark):
    return spark.read.json(
        spark.sparkContext.parallelize([json.dumps(product) for product in PRODUCTS])
    )


def test_raw_products_keeps_every_row_and_stamps_metadata(spark):
    captured = date(2026, 11, 15)

    rows = raw_products(
        read_products(spark), "70500123", "QFC Test Store", "eggs", captured
    ).collect()

    # No filtering: even Eggplant, Eggo and the unpriced row are Bronze material.
    assert len(rows) == len(PRODUCTS)
    by_description = {row.description: row for row in rows}
    assert set(by_description) == {product["description"] for product in PRODUCTS}

    eggs = by_description["Large Brown Eggs, 12 ct"]
    assert eggs.store_location_id == "70500123"
    assert eggs.store_name == "QFC Test Store"
    assert eggs.search_term == "eggs"
    assert eggs.captured_date == captured
    # The API payload is preserved untouched for later re-derivation.
    assert eggs.upc == "0001111060903"
    assert eggs.items[0]["price"]["regular"] == 5.99
    assert eggs.items[0]["inventory"]["stockLevel"] == "HIGH"


def test_egg_prices_flattens_and_filters(spark):
    rows = egg_prices(read_products(spark), "70500123", "QFC Test Store").collect()

    assert [row.description for row in rows] == [
        "Egg Whites, 16 oz",
        "Large Brown Eggs, 12 ct",
    ]
    promo = rows[0]
    assert promo.store_location_id == "70500123"
    assert promo.store_name == "QFC Test Store"
    assert promo.effective_price == 3.99
    assert promo.regular_price == 4.49
    assert promo.stock_level == "LOW"
    assert promo.captured_at is not None

    regular = rows[1]
    assert regular.promo_price == 0.0
    assert regular.effective_price == 5.99
