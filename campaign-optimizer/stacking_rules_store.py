"""Read/write access to the live stacking-rule config for the /api/stacking-rules
endpoints in extended_server.py.

Mirrors backend/core/rule_engine.py's BigQuery-backed config (same table,
same scope/config_json shape, same RULE_TYPE_METADATA) - duplicated rather
than shared because backend/ and campaign-optimizer/ are separate Cloud Run
deployables with separate Docker build contexts (see acos_policy.py's
docstring for the fuller explanation of why this codebase duplicates a few
small modules instead of sharing them).

Only the config storage is duplicated here, not the rule evaluation logic
(RULE_HANDLERS/apply_stacked_rules) - this service only needs to let a UI
read and write the config; backend/'s bid-optimizer job is the only thing
that ever evaluates it.
"""
import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_STACKING_RULES_TABLE = "amazon-ppc-bid-optimizer.amazon_ppc.stacking_rules_config"

# Keep in sync with backend/core/rule_engine.py's RULE_TYPE_METADATA.
RULE_TYPE_METADATA: Dict[str, Dict[str, Any]] = {
    "spend_cap_pause": {
        "label": "Spend cap pause",
        "description": "Pause a keyword once its trailing 30-day spend crosses a hard dollar cap.",
        "params": {"max_cost_30d": {"label": "Max 30d spend ($)", "type": "number", "default": 50.0}},
    },
    "off_peak_bid_reduction": {
        "label": "Off-peak bid reduction",
        "description": "Shave bids by a percentage outside a chosen peak-hours window.",
        "params": {
            "reduction_pct": {"label": "Reduction (0-1)", "type": "number", "default": 0.10},
            "peak_hours": {"label": "Peak hour windows ([[start,end],...])", "type": "hour_ranges", "default": [[16, 18], [18, 20], [20, 22]]},
        },
    },
    "weekend_bid_adjustment": {
        "label": "Weekend bid adjustment",
        "description": "Adjust bids by a percentage on Saturday/Sunday (negative lowers, positive raises).",
        "params": {"adjustment_pct": {"label": "Adjustment (-1 to 1)", "type": "number", "default": -0.15}},
    },
    "inventory_days_pause": {
        "label": "Inventory days pause",
        "description": "Pause a keyword when the advertised ASIN's inventory-days-of-supply drops below a floor. No-ops until inventory data is wired in.",
        "params": {"min_days": {"label": "Minimum days of supply", "type": "number", "default": 15}},
    },
}


class InvalidRuleError(ValueError):
    pass


def validate_rules(raw_rules: List[Dict[str, Any]]) -> None:
    """Reject a rule list containing an unknown type before it's saved -
    catching a typo here is a lot cheaper than catching it when the bid
    optimizer silently skips an unrecognized rule at 2am."""
    if not isinstance(raw_rules, list):
        raise InvalidRuleError("rules must be a list")
    for rule in raw_rules:
        if not isinstance(rule, dict) or "type" not in rule:
            raise InvalidRuleError("each rule must be an object with a 'type' field")
        if rule["type"] not in RULE_TYPE_METADATA:
            valid = ", ".join(RULE_TYPE_METADATA)
            raise InvalidRuleError(f"Unknown rule type '{rule['type']}'. Valid types: {valid}")


def _bigquery_client():
    from google.cloud import bigquery
    return bigquery.Client(project=os.getenv("GCP_PROJECT_ID", "amazon-ppc-bid-optimizer"))


def get_rules(scope: str) -> List[Dict[str, Any]]:
    """Raw rule list for one scope ('default' or a campaign_id). Empty list
    (not an error) when nothing has been saved for that scope yet."""
    try:
        from google.cloud import bigquery

        client = _bigquery_client()
        rows = list(
            client.query(
                f"SELECT config_json FROM `{_STACKING_RULES_TABLE}` WHERE scope = @scope LIMIT 1",
                job_config=bigquery.QueryJobConfig(
                    query_parameters=[bigquery.ScalarQueryParameter("scope", "STRING", scope)]
                ),
            ).result()
        )
    except Exception as exc:
        logger.warning(f"Failed to read stacking rules for scope '{scope}': {exc}")
        return []
    if not rows:
        return []
    return json.loads(rows[0].config_json)


def save_rules(scope: str, raw_rules: List[Dict[str, Any]]) -> None:
    """Persist a rule list for a scope, replacing whatever was there."""
    validate_rules(raw_rules)
    from google.cloud import bigquery

    client = _bigquery_client()
    query = f"""
        MERGE `{_STACKING_RULES_TABLE}` T
        USING (SELECT @scope AS scope, @config_json AS config_json, CURRENT_TIMESTAMP() AS updated_at) S
        ON T.scope = S.scope
        WHEN MATCHED THEN UPDATE SET config_json = S.config_json, updated_at = S.updated_at
        WHEN NOT MATCHED THEN INSERT (scope, config_json, updated_at)
          VALUES (S.scope, S.config_json, S.updated_at)
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("scope", "STRING", scope),
            bigquery.ScalarQueryParameter("config_json", "STRING", json.dumps(raw_rules)),
        ]
    )
    client.query(query, job_config=job_config).result()
