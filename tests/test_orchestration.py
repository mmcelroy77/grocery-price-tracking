import importlib
import tomllib
from pathlib import Path

from dagster import materialize

from grocery_price_tracking.common.storage import WriteStats, lake_uri
from grocery_price_tracking.jobs import qfc_grocery_job
from grocery_price_tracking.orchestration import definitions
from grocery_price_tracking.orchestration.definitions import kroger_bronze_products


def test_asset_records_the_write_stats_as_metadata(monkeypatch):
    monkeypatch.setattr(qfc_grocery_job, "run", lambda: WriteStats(4, 12, 2048, 1))

    result = materialize([kroger_bronze_products])

    assert result.success
    (event,) = result.get_asset_materialization_events()
    metadata = {k: v.value for k, v in event.materialization.metadata.items()}
    assert metadata == {
        "uri": lake_uri(qfc_grocery_job.OUTPUT),
        "delta_version": 4,
        "num_rows": 12,
        "num_bytes": 2048,
        "num_files": 1,
    }


def test_asset_is_registered_with_a_retry_policy():
    assets_def = definitions.defs.get_assets_def("kroger_bronze_products")

    assert assets_def.op.retry_policy == definitions.RETRY_POLICY


def test_pyproject_points_dagster_at_these_definitions():
    pyproject = tomllib.loads(Path("pyproject.toml").read_text())

    module = importlib.import_module(pyproject["tool"]["dagster"]["module_name"])

    assert module.defs is definitions.defs
