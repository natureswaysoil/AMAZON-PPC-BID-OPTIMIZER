-- One-time cleanup for duplicate Amazon Ads sync rows.
-- Replace {project_id} and {dataset} before running.
-- Run this once before deploying the staging/MERGE loader.

CREATE OR REPLACE TABLE `{project_id}.{dataset}.sp_keywords`
PARTITION BY sync_date
CLUSTER BY campaign_id, keyword_id AS
SELECT * EXCEPT (_row_number)
FROM (
  SELECT
    *,
    ROW_NUMBER() OVER (
      PARTITION BY keyword_id
      ORDER BY updated_at DESC, sync_date DESC
    ) AS _row_number
  FROM `{project_id}.{dataset}.sp_keywords`
)
WHERE _row_number = 1;

CREATE OR REPLACE TABLE `{project_id}.{dataset}.sp_campaign_performance`
PARTITION BY date
CLUSTER BY campaign_id AS
SELECT * EXCEPT (_row_number)
FROM (
  SELECT
    *,
    ROW_NUMBER() OVER (
      PARTITION BY campaign_id, date
      ORDER BY updated_at DESC
    ) AS _row_number
  FROM `{project_id}.{dataset}.sp_campaign_performance`
)
WHERE _row_number = 1;

CREATE OR REPLACE TABLE `{project_id}.{dataset}.sp_advertised_product_metrics`
PARTITION BY sync_date
CLUSTER BY campaign_id, asin AS
SELECT * EXCEPT (_row_number)
FROM (
  SELECT
    *,
    ROW_NUMBER() OVER (
      PARTITION BY campaign_id, ad_group_id, asin, sku
      ORDER BY updated_at DESC, sync_date DESC
    ) AS _row_number
  FROM `{project_id}.{dataset}.sp_advertised_product_metrics`
)
WHERE _row_number = 1;

-- search_term_reports is intentionally not rebuilt here because its current
-- schema is not defined in create_sync_tables.sql. The loader prevents new
-- duplicates; the next search-term normalization repair will add a canonical
-- schema and a safe cleanup for that table.
