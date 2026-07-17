-- scripts/create_stacking_rules_config_table.sql
-- Live-editable stacking-rule config, read by backend/core/rule_engine.py
-- and written by the /api/stacking-rules endpoint. One row per scope:
-- "default" for the account-wide rule set, or a specific campaign_id to
-- override it for that campaign. config_json holds the JSON list of
-- {"type", "enabled", "params"} objects (same shape as the bundled
-- backend/config/stacking_rules.json fallback used when this table has no
-- matching row, e.g. before it's been created or seeded).

CREATE TABLE IF NOT EXISTS `{project_id}.{dataset}.stacking_rules_config` (
  scope STRING NOT NULL,
  config_json STRING NOT NULL,
  updated_at TIMESTAMP
)
CLUSTER BY scope;
