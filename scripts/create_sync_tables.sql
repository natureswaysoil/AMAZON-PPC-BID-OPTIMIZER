-- scripts/create_sync_tables.sql
-- Creates all tables needed for Amazon Ads data sync

-- Campaigns table
CREATE TABLE IF NOT EXISTS `{project_id}.{dataset}.sp_campaigns` (
    campaign_id INT64 NOT NULL,
    campaign_name STRING,
    campaign_status STRING,
    campaign_type STRING,
    daily_budget FLOAT64,
    start_date DATE,
    end_date DATE,
    updated_at TIMESTAMP
);

-- Keywords table
CREATE TABLE IF NOT EXISTS `{project_id}.{dataset}.sp_keywords` (
    keyword_id INT64 NOT NULL,
    campaign_id INT64,
    ad_group_id INT64,
    keyword_text STRING,
    match_type STRING,
    bid FLOAT64,
    state STRING,
    updated_at TIMESTAMP
);

-- Campaign performance table (partitioned by date)
CREATE TABLE IF NOT EXISTS `{project_id}.{dataset}.sp_campaign_performance` (
    date DATE NOT NULL,
    campaign_id INT64,
    impressions INT64,
    clicks INT64,
    cost FLOAT64,
    sales FLOAT64,
    purchases INT64,
    updated_at TIMESTAMP
)
PARTITION BY date
CLUSTER BY campaign_id;

-- Keyword performance table (partitioned by date)
CREATE TABLE IF NOT EXISTS `{project_id}.{dataset}.keyword_performance` (
    date DATE NOT NULL,
    keyword_id INT64,
    campaign_id INT64,
    ad_group_id INT64,
    impressions INT64,
    clicks INT64,
    cost FLOAT64,
    conversion_value FLOAT64,
    conversions INT64,
    updated_at TIMESTAMP
)
PARTITION BY date
CLUSTER BY keyword_id, campaign_id;

-- Advertised product metrics (for AOV calculation)
CREATE TABLE IF NOT EXISTS `{project_id}.{dataset}.sp_advertised_product_metrics` (
    campaign_id INT64 NOT NULL,
    date DATE NOT NULL,
    aov FLOAT64,
    orders INT64,
    revenue FLOAT64,
    updated_at TIMESTAMP
)
PARTITION BY date
CLUSTER BY campaign_id;
