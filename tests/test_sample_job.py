import runpy
import sys
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def prices_csv(tmp_path):
    path = tmp_path / "prices.csv"
    path.write_text("item,price\nmilk,3.0\nmilk,4.0\neggs,5.0\n")
    return path


def test_sample_job_main(spark, prices_csv, monkeypatch, capsys):
    # Wrap the shared session so the job's spark.stop() doesn't kill it for other tests.
    job_spark = MagicMock(wraps=spark)
    job_spark.stop = MagicMock()
    monkeypatch.setattr(
        "grocery_price_tracking.spark.get_spark", lambda _name: job_spark
    )
    monkeypatch.setattr(sys, "argv", ["sample_job", "--input", str(prices_csv)])

    # run_name="__main__" also covers the `if __name__ == "__main__"` guard.
    runpy.run_module("grocery_price_tracking.jobs.sample_job", run_name="__main__")

    assert "milk" in capsys.readouterr().out
    job_spark.stop.assert_called_once()
