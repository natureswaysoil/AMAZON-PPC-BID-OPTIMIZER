"""Idempotent BigQuery loading helpers.

Reports are first loaded into a short-lived staging table, then merged into the
production table using a stable business key. Re-running the same Amazon report
updates the existing row instead of appending a duplicate.
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Sequence

from google.cloud import bigquery

logger = logging.getLogger(__name__)

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

TABLE_KEYS: Dict[str, Sequence[str]] = {
    "sp_keywords": ("keyword_id", "sync_date"),
    "sp_campaign_performance": ("campaign_id", "date"),
    "sp_advertised_product_metrics": (
        "campaign_id",
        "ad_group_id",
        "asin",
        "sku",
        "sync_date",
    ),
    "search_term_reports": (
        "campaignId",
        "adGroupId",
        "keywordId",
        "searchTerm",
        "date",
    ),
}


def _quote(identifier: str) -> str:
    """Quote a validated BigQuery column identifier."""
    if not _IDENTIFIER.fullmatch(identifier):
        raise ValueError(f"Unsafe BigQuery identifier: {identifier!r}")
    return f"`{identifier}`"


def build_merge_sql(
    target_table: str,
    staging_table: str,
    columns: Sequence[str],
    key_columns: Sequence[str],
) -> str:
    """Build a null-safe BigQuery MERGE statement."""
    if not columns:
        raise ValueError("At least one column is required for a MERGE")
    if not key_columns:
        raise ValueError("At least one key column is required for a MERGE")

    missing = [column for column in key_columns if column not in columns]
    if missing:
        raise ValueError(f"MERGE keys are absent from the payload: {missing}")

    on_parts = [
        f"(T.{_quote(column)} = S.{_quote(column)} OR "
        f"(T.{_quote(column)} IS NULL AND S.{_quote(column)} IS NULL))"
        for column in key_columns
    ]
    update_columns = [column for column in columns if column not in key_columns]
    update_clause = ",\n      ".join(
        f"T.{_quote(column)} = S.{_quote(column)}" for column in update_columns
    )
    insert_columns = ", ".join(_quote(column) for column in columns)
    insert_values = ", ".join(f"S.{_quote(column)}" for column in columns)

    matched_clause = ""
    if update_columns:
        matched_clause = f"""
WHEN MATCHED THEN
  UPDATE SET
      {update_clause}"""

    return f"""MERGE `{target_table}` AS T
USING `{staging_table}` AS S
ON {' AND '.join(on_parts)}{matched_clause}
WHEN NOT MATCHED THEN
  INSERT ({insert_columns})
  VALUES ({insert_values})
"""


class BigQueryUpsertLoader:
    """Load JSON rows into BigQuery without duplicating report snapshots."""

    def __init__(self, client: bigquery.Client, project_id: str, dataset: str):
        self.client = client
        self.project_id = project_id
        self.dataset = dataset

    def load(self, table_name: str, rows: List[Dict[str, Any]]) -> Dict[str, int]:
        """Stage and merge rows into ``table_name``.

        Returns counts useful for job logs. The source row count is exact;
        BigQuery DML statistics are included when the client exposes them.
        """
        if not rows:
            return {"source_rows": 0, "affected_rows": 0}
        if table_name not in TABLE_KEYS:
            raise ValueError(f"No deduplication key configured for {table_name}")

        columns = list(rows[0].keys())
        inconsistent = [index for index, row in enumerate(rows) if set(row) != set(columns)]
        if inconsistent:
            raise ValueError(
                "All rows must have the same columns; inconsistent rows at indexes "
                f"{inconsistent[:10]}"
            )

        target_id = f"{self.project_id}.{self.dataset}.{table_name}"
        staging_name = f"_staging_{table_name}_{uuid.uuid4().hex[:12]}"
        staging_id = f"{self.project_id}.{self.dataset}.{staging_name}"

        target = self.client.get_table(target_id)
        staging = bigquery.Table(staging_id, schema=target.schema)
        staging.expires = datetime.now(timezone.utc) + timedelta(hours=2)
        self.client.create_table(staging)

        try:
            load_config = bigquery.LoadJobConfig(
                write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
                source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
                schema=target.schema,
            )
            load_job = self.client.load_table_from_json(
                rows,
                staging_id,
                job_config=load_config,
            )
            load_job.result()

            merge_sql = build_merge_sql(
                target_table=target_id,
                staging_table=staging_id,
                columns=columns,
                key_columns=TABLE_KEYS[table_name],
            )
            merge_job = self.client.query(merge_sql)
            merge_job.result()
            affected = int(getattr(merge_job, "num_dml_affected_rows", 0) or 0)
            logger.info(
                "Merged %s source rows into %s (%s affected rows)",
                len(rows),
                target_id,
                affected,
            )
            return {"source_rows": len(rows), "affected_rows": affected}
        finally:
            self.client.delete_table(staging_id, not_found_ok=True)
