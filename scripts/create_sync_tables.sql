-- scripts/create_sync_tables.sql
-- BigQuery table schemas for Amazon Ads data sync

-- Keywords table (30-day performance summary)
CREATE TABLE IF NOT EXISTS `{project_id}.{dataset}.sp_keywords` (
  keyword_id INT64 NOT NULL,
  keyword_text STRING,
  keyword_bid FLOAT64,
  match_type STRING,
  campaign_id INT64,
  campaign_name STRING,
  ad_group_id INT64,
  ad_group_name STRING,
  
  -- Performance metrics (30d)
  impressions INT64,
  clicks INT64,
  cost FLOAT64,
  purchases INT64,
  sales FLOAT64,
  purchases_1d INT64,
  purchases_7d INT64,
  purchases_14d INT64,
  purchases_30d INT64,
  
  -- Calculated metrics
  ctr FLOAT64,
  cvr FLOAT64,
  acos FLOAT64,
  
  sync_date DATE,
  updated_at TIMESTAMP
)
PARTITION BY sync_date
CLUSTER BY campaign_id, keyword_id;

-- Campaign performance table (daily)
CREATE TABLE IF NOT EXISTS `{project_id}.{dataset}.sp_campaign_performance` (
  campaign_id INT64 NOT NULL,
  campaign_name STRING,
  campaign_status STRING,
  campaign_budget FLOAT64,
  date DATE NOT NULL,
  
  impressions INT64,
  clicks INT64,
  cost FLOAT64,
  purchases INT64,
  sales FLOAT64,
  acos FLOAT64,
  roas FLOAT64,
  
  updated_at TIMESTAMP
)
PARTITION BY date
CLUSTER BY campaign_id;

-- Advertised product metrics (for AOV calculation)
CREATE TABLE IF NOT EXISTS `{project_id}.{dataset}.sp_advertised_product_metrics` (
  campaign_id INT64,
  ad_group_id INT64,
  asin STRING,
  sku STRING,
  
  impressions INT64,
  clicks INT64,
  cost FLOAT64,
  purchases INT64,
  sales FLOAT64,
  units_sold INT64,
  
  -- AOV calculation (will be computed by BigQuery)
  -- aov = sales / purchases when purchases > 0
  
  sync_date DATE,
  updated_at TIMESTAMP
)
PARTITION BY sync_date
CLUSTER BY campaign_id, asin;

-- Example usage:
-- Replace {project_id} and {dataset} with your values
-- For example:
-- sed 's/{project_id}/amazon-ppc-bid-optimizer/g; s/{dataset}/amazon_ppc/g' create_sync_tables.sql | bq query --use_legacy_sql=false
