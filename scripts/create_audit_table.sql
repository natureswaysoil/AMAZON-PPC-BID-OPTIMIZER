-- scripts/create_audit_table.sql
-- Audit log for bid optimization decisions

CREATE TABLE IF NOT EXISTS `{project_id}.{dataset}.bid_optimization_log` (
  keyword_id INT64 NOT NULL,
  keyword_text STRING,
  campaign_id INT64,
  ad_group_id INT64,
  
  -- Bid values
  current_bid FLOAT64,
  final_bid FLOAT64,
  suggested_bid FLOAT64,
  aov_bid FLOAT64,
  ceiling FLOAT64,
  
  -- Classification
  aov FLOAT64,
  aov_confidence STRING,
  aov_tier STRING,
  performance_tier STRING,
  
  -- Decision metadata
  blend_method STRING,
  reasoning STRING,
  hour_of_day INT64,
  timestamp TIMESTAMP,
  
  -- Partition and cluster for query performance
  run_date DATE GENERATED ALWAYS AS (DATE(timestamp)) STORED
)
PARTITION BY run_date
CLUSTER BY campaign_id, aov_tier, performance_tier;
