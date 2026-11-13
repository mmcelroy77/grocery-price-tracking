import runpy
from unittest.mock import MagicMock

from grocery_price_tracking.common.storage import lake_uri, read_delta


def test_sample_job_main(spark, monkeypatch, capsys):
    # Reads the committed data/raw/prices.csv; writes under the temp lake root.
    # Wrap the shared session so the job's spark.stop() doesn't kill it for other tests.
    job_spark = MagicMock(wraps=spark)
    job_spark.stop = MagicMock()
    monkeypatch.setattr(
        "grocery_price_tracking.spark.get_spark", lambda _name: job_spark
    )

    # run_name="__main__" also covers the `if __name__ == "__main__"` guard.
    job = runpy.run_module(
        "grocery_price_tracking.jobs.sample_job", run_name="__main__"
    )

    out = capsys.readouterr().out
    assert "milk" in out
    uri = lake_uri(job["OUTPUT"])
    assert "Wrote 2 rows" in out and f"to {uri} as version 0" in out
    job_spark.stop.assert_called_once()
    rows = read_delta(spark, uri).orderBy("item").collect()
    assert [(r.item, r.avg_price) for r in rows] == [("eggs", 4.99), ("milk", 3.46)]
