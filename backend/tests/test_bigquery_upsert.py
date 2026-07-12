"""Tests for idempotent BigQuery report loading."""
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.bigquery_upsert import BigQueryUpsertLoader, TABLE_KEYS, build_merge_sql


def test_rolling_summary_keys_do_not_include_sync_date():
    assert TABLE_KEYS["sp_keywords"] == ("keyword_id",)
    assert "sync_date" not in TABLE_KEYS["sp_advertised_product_metrics"]
    assert "date" not in TABLE_KEYS["search_term_reports"]


def test_daily_campaign_key_includes_report_date():
    assert TABLE_KEYS["sp_campaign_performance"] == ("campaign_id", "date")


def test_build_merge_sql_updates_existing_and_inserts_new_rows():
    sql = build_merge_sql(
        "project.dataset.sp_keywords",
        "project.dataset._staging_sp_keywords_123",
        ["keyword_id", "cost", "sync_date"],
        ["keyword_id"],
    )
    assert "MERGE `project.dataset.sp_keywords` AS T" in sql
    assert "T.`keyword_id` = S.`keyword_id`" in sql
    assert "WHEN MATCHED THEN" in sql
    assert "T.`cost` = S.`cost`" in sql
    assert "T.`sync_date` = S.`sync_date`" in sql
    assert "WHEN NOT MATCHED THEN" in sql


def test_build_merge_sql_rejects_missing_key_column():
    with pytest.raises(ValueError, match="absent from the payload"):
        build_merge_sql(
            "project.dataset.table",
            "project.dataset.staging",
            ["cost"],
            ["keyword_id"],
        )


def test_loader_stages_merges_and_deletes_staging_table():
    client = MagicMock()
    client.get_table.return_value = SimpleNamespace(schema=["schema-field"])
    client.create_table.side_effect = lambda table: table

    load_job = MagicMock()
    query_job = MagicMock()
    query_job.num_dml_affected_rows = 1
    client.load_table_from_json.return_value = load_job
    client.query.return_value = query_job

    loader = BigQueryUpsertLoader(client, "project", "dataset")
    result = loader.load(
        "sp_keywords",
        [{"keyword_id": 123, "cost": 8.5, "sync_date": "2026-07-12"}],
    )

    assert result == {"source_rows": 1, "affected_rows": 1}
    load_job.result.assert_called_once()
    query_job.result.assert_called_once()
    merge_sql = client.query.call_args.args[0]
    assert "ON (T.`keyword_id` = S.`keyword_id`" in merge_sql
    client.delete_table.assert_called_once()
    assert client.delete_table.call_args.kwargs["not_found_ok"] is True


def test_loader_cleans_up_staging_table_when_merge_fails():
    client = MagicMock()
    client.get_table.return_value = SimpleNamespace(schema=["schema-field"])
    client.create_table.side_effect = lambda table: table
    client.load_table_from_json.return_value = MagicMock()
    client.query.side_effect = RuntimeError("merge failed")

    loader = BigQueryUpsertLoader(client, "project", "dataset")
    with pytest.raises(RuntimeError, match="merge failed"):
        loader.load(
            "sp_keywords",
            [{"keyword_id": 123, "cost": 8.5, "sync_date": "2026-07-12"}],
        )

    client.delete_table.assert_called_once()


def test_loader_rejects_inconsistent_row_shapes():
    loader = BigQueryUpsertLoader(MagicMock(), "project", "dataset")
    with pytest.raises(ValueError, match="same columns"):
        loader.load(
            "sp_keywords",
            [
                {"keyword_id": 1, "cost": 1.0},
                {"keyword_id": 2, "sales": 2.0},
            ],
        )
