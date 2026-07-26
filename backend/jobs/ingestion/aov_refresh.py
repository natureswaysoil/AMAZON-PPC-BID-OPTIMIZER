"""Refresh campaign-level 14-day and 30-day average order values."""

from datetime import datetime
import logging

from google.cloud import bigquery

from core.config import settings


logger = logging.getLogger(__name__)


def _build_keyword_performance_query() -> str:
    table = f"`{settings.PROJECT_ID}.{settings.BIGQUERY_DATASET}.keyword_performance`"
    return f"""
    WITH aov14 AS (
      SELECT
        tenant_id,
        campaign_id,
        SAFE_DIVIDE(SUM(conversion_value), NULLIF(SUM(conversions), 0)) AS aov_14d,
        SUM(conversions) AS conv_14d,
        SUM(conversion_value) AS sales_14d
      FROM {table}
      WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 14 DAY)
      GROUP BY tenant_id, campaign_id
    ), aov30 AS (
      SELECT
        tenant_id,
        campaign_id,
        SAFE_DIVIDE(SUM(conversion_value), NULLIF(SUM(conversions), 0)) AS aov_30d,
        SUM(conversions) AS conv_30d,
        SUM(conversion_value) AS sales_30d
      FROM {table}
      WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
      GROUP BY tenant_id, campaign_id
    )
    SELECT
      a14.tenant_id,
      a14.campaign_id,
      a14.aov_14d,
      a30.aov_30d,
      a14.conv_14d,
      a30.conv_30d,
      a14.sales_14d,
      a30.sales_30d,
      CURRENT_TIMESTAMP() AS updated_at
    FROM aov14 a14
    LEFT JOIN aov30 a30 USING (tenant_id, campaign_id)
    """


def _build_placement_fallback_query() -> str:
    placements = f"`{settings.PROJECT_ID}.{settings.BIGQUERY_DATASET}.placement_performance`"
    keywords = f"`{settings.PROJECT_ID}.{settings.BIGQUERY_DATASET}.keywords`"
    return f"""
    WITH mapped AS (
      SELECT
        p.tenant_id,
        k.campaign_id,
        p.date,
        p.conversions,
        p.conversion_value
      FROM {placements} p
      JOIN {keywords} k
        ON k.keyword_id = SAFE_CAST(p.keyword_id AS INT64)
       AND COALESCE(k.tenant_id, '') = COALESCE(p.tenant_id, '')
    ), p14 AS (
      SELECT
        tenant_id,
        campaign_id,
        SAFE_DIVIDE(SUM(conversion_value), NULLIF(SUM(conversions), 0)) AS aov_14d,
        SUM(conversions) AS conv_14d,
        SUM(conversion_value) AS sales_14d
      FROM mapped
      WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 14 DAY)
      GROUP BY tenant_id, campaign_id
    ), p30 AS (
      SELECT
        tenant_id,
        campaign_id,
        SAFE_DIVIDE(SUM(conversion_value), NULLIF(SUM(conversions), 0)) AS aov_30d,
        SUM(conversions) AS conv_30d,
        SUM(conversion_value) AS sales_30d
      FROM mapped
      WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
      GROUP BY tenant_id, campaign_id
    )
    SELECT
      p14.tenant_id,
      p14.campaign_id,
      p14.aov_14d,
      p30.aov_30d,
      p14.conv_14d,
      p30.conv_30d,
      p14.sales_14d,
      p30.sales_30d,
      CURRENT_TIMESTAMP() AS updated_at
    FROM p14
    LEFT JOIN p30 USING (tenant_id, campaign_id)
    """


def run_aov_refresh() -> None:
    """Refresh campaign AOV data and propagate failures to the job runner."""
    logger.info("Refreshing campaign AOV aggregates (14d/30d)...")
    client = bigquery.Client(project=settings.PROJECT_ID)
    table_id = f"{settings.PROJECT_ID}.{settings.BIGQUERY_DATASET}.campaign_aov"

    rows = list(client.query(_build_keyword_performance_query()).result())
    if not rows:
        logger.info(
            "No keyword_performance rows found; using placement_performance fallback"
        )
        rows = list(client.query(_build_placement_fallback_query()).result())

    payload = []
    for row in rows:
        record = dict(row)
        timestamp = record.get("updated_at")
        if isinstance(timestamp, datetime):
            record["updated_at"] = timestamp.isoformat()
        payload.append(record)

    if not payload:
        logger.info("No AOV data found to refresh")
        return

    load_job = client.load_table_from_json(
        payload,
        table_id,
        job_config=bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE"),
    )
    load_job.result()
    logger.info("Refreshed campaign_aov with %d records", len(payload))
