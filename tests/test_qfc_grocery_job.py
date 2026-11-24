import runpy
import sys
from datetime import date
from unittest.mock import MagicMock

import pytest

from grocery_price_tracking.common import kroger
from grocery_price_tracking.common.storage import lake_uri, read_delta

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
]

MILK = [
    {
        "productId": "0001111060906",
        "upc": "0001111060906",
        "brand": "Kroger",
        "description": "Whole Milk, 1 gal",
        "items": [
            {
                "size": "1 gal",
                "price": {"regular": 3.99, "promo": 0},
                "inventory": {"stockLevel": "HIGH"},
            }
        ],
    }
]
BREAD = [
    {
        "productId": "0001111060907",
        "upc": "0001111060907",
        "brand": "Kroger",
        "description": "Whole Wheat Bread, 20 oz",
        "items": [
            {
                "size": "20 oz",
                "price": {"regular": 2.49, "promo": 0},
                "inventory": {"stockLevel": "HIGH"},
            }
        ],
    }
]
BY_TERM = {"eggs": PRODUCTS, "milk": MILK, "bread": BREAD}


def mock_job(spark, monkeypatch, by_term=BY_TERM, run_name="__main__"):
    """Run the job with a wrapped session and stubbed Kroger calls.

    by_term maps each search term to the products the stubbed API returns for it.

    The default run_name runs main(), like `gpt-grocery`. Any other name only loads the
    module, so a test can call job["run"]() itself.
    """
    # Wrap the shared session so the job's spark.stop() doesn't kill it for other tests.
    job_spark = MagicMock(wraps=spark)
    job_spark.stop = MagicMock()
    monkeypatch.setattr(
        "grocery_price_tracking.spark.get_spark", lambda _name: job_spark
    )
    monkeypatch.setattr(kroger, "credentials_from_env", lambda: ("id", "secret"))
    monkeypatch.setattr(kroger, "load_dotenv", lambda: None)
    monkeypatch.setattr(kroger, "get_access_token", lambda _id, _secret: "token")
    monkeypatch.setattr(
        kroger,
        "find_store",
        lambda _token, _zip, _chain: {
            "locationId": "70500123",
            "name": "QFC Test Store",
        },
    )
    monkeypatch.setattr(
        kroger, "search_products", lambda _token, term, _location_id: by_term[term]
    )
    # Other tests import the module; runpy warns if it is already loaded.
    name = "grocery_price_tracking.jobs.qfc_grocery_job"
    monkeypatch.delitem(sys.modules, name, raising=False)
    job = runpy.run_module(name, run_name=run_name)
    return job, job_spark


def test_qfc_grocery_job_writes_todays_bronze_snapshot(
    spark, monkeypatch, capsys, lake_root
):
    job, job_spark = mock_job(spark, monkeypatch)

    out = capsys.readouterr().out
    captured = date.today()
    uri = lake_uri(job["OUTPUT"])
    assert "QFC Test Store (70500123)" in out
    assert f"5 products captured for {captured}" in out
    assert "Wrote 5 rows" in out and f"to {uri} as version 0" in out
    job_spark.stop.assert_called_once()

    rows = read_delta(spark, uri).orderBy("description").collect()
    # Bronze keeps every product, including the ones the egg filter drops.
    assert [(row.search_term, row.description) for row in rows] == [
        ("eggs", "Egg Whites, 16 oz"),
        ("eggs", "Eggplant"),
        ("eggs", "Large Brown Eggs, 12 ct"),
        ("milk", "Whole Milk, 1 gal"),
        ("bread", "Whole Wheat Bread, 20 oz"),
    ]
    assert {row.store_location_id for row in rows} == {"70500123"}
    assert {row.store_name for row in rows} == {"QFC Test Store"}
    assert {row.captured_date for row in rows} == {captured}

    # The table is partitioned by day.
    day = lake_root / job["OUTPUT"] / f"captured_date={captured.isoformat()}"
    assert list(day.glob("*.parquet"))


def test_run_returns_the_write_stats(spark, monkeypatch):
    job, _ = mock_job(spark, monkeypatch, run_name="qfc_grocery_job")

    stats = job["run"]()

    assert (stats.version, stats.num_rows) == (0, 5)


def test_qfc_grocery_job_rerun_replaces_the_same_day_and_adds_new_columns(
    spark, monkeypatch, capsys
):
    mock_job(spark, monkeypatch)
    capsys.readouterr()
    # A new field in the API response becomes a new column instead of failing.
    with_new_field = {
        term: [{**product, "newField": "x"} for product in products]
        for term, products in BY_TERM.items()
    }
    job, _ = mock_job(spark, monkeypatch, by_term=with_new_field)

    out = capsys.readouterr().out
    uri = lake_uri(job["OUTPUT"])
    assert "Wrote 5 rows" in out and f"to {uri} as version 1" in out
    table = read_delta(spark, uri)
    assert table.count() == 5
    assert "newField" in table.columns


def test_qfc_grocery_job_fails_on_empty_search(spark, monkeypatch, lake_root):
    with pytest.raises(RuntimeError, match="no eggs products"):
        mock_job(spark, monkeypatch, by_term={**BY_TERM, "eggs": []})

    assert not (lake_root / "bronze").exists()
