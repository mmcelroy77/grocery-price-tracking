from grocery_price_tracking.transforms.prices import avg_price_by_item


def test_avg_price_by_item(spark):
    df = spark.createDataFrame(
        [("milk", 3.0), ("milk", 4.0), ("eggs", 5.0)], ["item", "price"]
    )
    rows = {r["item"]: r for r in avg_price_by_item(df).collect()}

    assert rows["milk"]["avg_price"] == 3.5
    assert rows["milk"]["min_price"] == 3.0
    assert rows["eggs"]["max_price"] == 5.0
