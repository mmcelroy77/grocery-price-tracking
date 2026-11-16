import runpy
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


def mock_job(spark, monkeypatch, products=PRODUCTS):
    """Run the job with a wrapped session and stubbed Kroger calls."""
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
        kroger, "search_products", lambda _token, _term, _location_id: products
    )
    job = runpy.run_module(
        "grocery_price_tracking.jobs.qfc_eggs_job", run_name="__main__"
    )
    return job, job_spark


def test_qfc_eggs_job_writes_todays_bronze_snapshot(spark, monkeypatch, capsys):
    job, job_spark = mock_job(spark, monkeypatch)

    out = capsys.readouterr().out
    captured = date.today()
    uri = lake_uri(job["OUTPUT"])
    assert "QFC Test Store (70500123)" in out
    assert f"3 products captured for {captured}" in out
    assert "Wrote 3 rows" in out and f"to {uri} as version 0" in out
    job_spark.stop.assert_called_once()

    rows = read_delta(spark, uri).orderBy("description").collect()
    # Bronze keeps every product, including the ones the egg filter drops.
    assert [row.description for row in rows] == [
        "Egg Whites, 16 oz",
        "Eggplant",
        "Large Brown Eggs, 12 ct",
    ]
    assert {row.store_location_id for row in rows} == {"70500123"}
    assert {row.store_name for row in rows} == {"QFC Test Store"}
    assert {row.search_term for row in rows} == {"eggs"}
    assert {row.captured_date for row in rows} == {captured}


def test_qfc_eggs_job_partitions_by_captured_date(spark, monkeypatch, lake_root):
    job, _ = mock_job(spark, monkeypatch)

    table = lake_root / job["OUTPUT"]
    day = table / f"captured_date={date.today().isoformat()}"
    assert day.is_dir()
    assert list(day.glob("*.parquet"))


def test_qfc_eggs_job_rerun_replaces_the_same_day(spark, monkeypatch, capsys):
    mock_job(spark, monkeypatch)
    capsys.readouterr()
    job, _ = mock_job(spark, monkeypatch)

    out = capsys.readouterr().out
    uri = lake_uri(job["OUTPUT"])
    assert "Wrote 3 rows" in out and f"to {uri} as version 1" in out
    assert read_delta(spark, uri).count() == 3


def test_qfc_eggs_job_fails_on_empty_search(spark, monkeypatch, lake_root):
    with pytest.raises(RuntimeError, match="no eggs products"):
        mock_job(spark, monkeypatch, products=[])

    assert not (lake_root / "bronze").exists()
