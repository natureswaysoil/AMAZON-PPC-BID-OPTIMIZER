"""Stackable rules layered on top of the ACOS-tier bid decision.

A tenant's base bid decision comes from AOVBidOptimizer.calculate_optimal_bid
(AOV tier + performance tier + ACOS-vs-target). Rules in this module are
optional, composable conditions applied *after* that base decision - e.g.
"also pause if inventory is running low" or "also shave bids off-peak".
Each rule is independent and order-preserving: a tenant can enable any
subset, in any order, without the rule types needing to know about each
other. Deliberately not an open-ended rule builder - see RULE_HANDLERS for
the fixed set of supported types.

Every rule is opt-in (enabled defaults to False in config) so shipping this
module changes no live behavior until a tenant/admin turns a rule on.
"""
import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "stacking_rules.json"

_STACKING_RULES_TABLE = "amazon-ppc-bid-optimizer.amazon_ppc.stacking_rules_config"
_BQ_CACHE_TTL_SECONDS = 900
_bq_cache: Dict[str, Any] = {}  # scope -> (raw_rules_or_None, fetched_at)

# Metadata for each rule type, used to render/validate the config UI. Kept
# next to RULE_HANDLERS (not derived from it) since a handler's Python
# signature doesn't say what its params mean or which are required - this is
# the single source of truth for that; campaign-optimizer/stacking_rules_store.py
# duplicates this (not the evaluation logic) for the same reason acos_policy.py
# is duplicated between the two services (see that file's docstring).
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


@dataclass
class Rule:
    type: str
    enabled: bool = False
    params: Dict[str, Any] = field(default_factory=dict)


def _pause(decision: Dict[str, Any], min_bid: float, note: str) -> None:
    decision["new_bid"] = round(min_bid, 2)
    decision["pause_recommended"] = True
    decision["reasoning"] += f" | Rule: {note}"


def _rule_inventory_days_pause(decision: Dict[str, Any], keyword_data: Dict[str, Any], ctx: Dict[str, Any], params: Dict[str, Any]) -> None:
    """Pause if inventory-days-of-supply for the advertised ASIN drops below a
    floor. No-ops when inventory data isn't available yet (this codebase has
    no inventory feed wired in as of this writing) rather than guessing."""
    days_supply = keyword_data.get("inventory_days_supply")
    if days_supply is None:
        return
    min_days = float(params.get("min_days", 15))
    if float(days_supply) < min_days:
        _pause(decision, ctx["min_bid"], f"inventory_days_pause ({days_supply:.0f}d < {min_days:.0f}d floor)")


def _rule_spend_cap_pause(decision: Dict[str, Any], keyword_data: Dict[str, Any], ctx: Dict[str, Any], params: Dict[str, Any]) -> None:
    """Pause if trailing spend for this keyword exceeds a hard cap, independent
    of the ACOS-based zero-order gates (those look at clicks/conversions;
    this looks at raw dollars, e.g. a low-clicks/high-CPC keyword that
    burned budget fast)."""
    max_cost = params.get("max_cost_30d")
    if max_cost is None:
        return
    cost_30d = float(keyword_data.get("cost_30d") or 0)
    if cost_30d >= float(max_cost):
        _pause(decision, ctx["min_bid"], f"spend_cap_pause (${cost_30d:.2f} >= ${float(max_cost):.2f} cap)")


def _rule_off_peak_bid_reduction(decision: Dict[str, Any], keyword_data: Dict[str, Any], ctx: Dict[str, Any], params: Dict[str, Any]) -> None:
    """Shave the computed bid by a tenant-configurable percentage outside a
    tenant-configurable peak-hours window. Separate knob from the system's
    built-in prime-hour multiplier baked into the ceiling calc - this is an
    additional, opt-in layer a tenant stacks on top."""
    hour = ctx.get("hour")
    if hour is None or decision.get("pause_recommended"):
        return
    peak_hours = params.get("peak_hours") or []
    is_peak = any(start <= hour < end for start, end in peak_hours)
    if is_peak:
        return
    reduction_pct = float(params.get("reduction_pct", 0.10))
    new_bid = decision["new_bid"] * (1 - reduction_pct)
    decision["new_bid"] = round(max(ctx["min_bid"], new_bid), 2)
    decision["reasoning"] += f" | Rule: off_peak_bid_reduction (-{reduction_pct:.0%} outside peak hours)"


def _rule_weekend_bid_adjustment(decision: Dict[str, Any], keyword_data: Dict[str, Any], ctx: Dict[str, Any], params: Dict[str, Any]) -> None:
    """Adjust bids on weekends by a tenant-configurable percentage (positive
    to bid up, negative to bid down). Separate axis from off_peak_bid_reduction
    (hour-of-day) since weekend traffic patterns don't always match weekday
    off-peak patterns."""
    weekday = ctx.get("weekday")
    if weekday is None or decision.get("pause_recommended"):
        return
    if weekday < 5:  # Monday=0 .. Sunday=6
        return
    adjustment_pct = float(params.get("adjustment_pct", -0.15))
    new_bid = decision["new_bid"] * (1 + adjustment_pct)
    decision["new_bid"] = round(max(ctx["min_bid"], new_bid), 2)
    decision["reasoning"] += f" | Rule: weekend_bid_adjustment ({adjustment_pct:+.0%} on weekends)"


RULE_HANDLERS: Dict[str, Callable[[Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any]], None]] = {
    "inventory_days_pause": _rule_inventory_days_pause,
    "spend_cap_pause": _rule_spend_cap_pause,
    "off_peak_bid_reduction": _rule_off_peak_bid_reduction,
    "weekend_bid_adjustment": _rule_weekend_bid_adjustment,
}


def apply_stacked_rules(
    decision: Dict[str, Any],
    keyword_data: Dict[str, Any],
    rules: List[Rule],
    hour: Optional[int] = None,
    weekday: Optional[int] = None,
    min_bid: float = 0.02,
    max_bid: Optional[float] = None,
) -> Dict[str, Any]:
    """Apply enabled rules, in order, to a base decision from
    calculate_optimal_bid. Rules run after the base decision's own rails, so
    the final clamp below re-enforces the global min/max after stacking -
    it does not re-apply the per-run movement rails, since a stacked rule is
    an intentional additional layer, not part of the base tier logic."""
    ctx = {"hour": hour, "weekday": weekday, "min_bid": min_bid}
    for rule in rules:
        if not rule.enabled:
            continue
        handler = RULE_HANDLERS.get(rule.type)
        if handler is None:
            logger.warning(f"Unknown stacking rule type '{rule.type}', skipping")
            continue
        try:
            handler(decision, keyword_data, ctx, rule.params)
        except Exception as exc:
            logger.warning(f"Stacking rule '{rule.type}' failed, leaving decision unchanged: {exc}")

    decision["new_bid"] = max(min_bid, decision["new_bid"])
    if max_bid is not None:
        decision["new_bid"] = min(max_bid, decision["new_bid"])
    decision["new_bid"] = round(decision["new_bid"], 2)
    return decision


def _load_json_config() -> Dict[str, Any]:
    """Last-resort fallback when BigQuery has no row for a scope (or is
    unreachable, e.g. local/offline dev) - the file this module shipped with
    before live editing existed."""
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"default": [], "per_campaign": {}}
    except Exception as exc:
        logger.warning(f"Failed to read {CONFIG_PATH}, no stacking rules will apply: {exc}")
        return {"default": [], "per_campaign": {}}


def _rules_from_list(raw_rules: List[Dict[str, Any]]) -> List[Rule]:
    return [
        Rule(type=r["type"], enabled=bool(r.get("enabled", False)), params=r.get("params", {}))
        for r in raw_rules
    ]


def _get_raw_rules_from_bigquery(scope: str) -> Optional[List[Dict[str, Any]]]:
    """Raw (pre-Rule-object) config for one scope ('default' or a campaign_id),
    or None if no row exists for that scope. Cached in-process for 15 minutes,
    same TTL as acos_policy.get_target_acos(), so a live-editing UI's save
    shows up within that window rather than needing a redeploy."""
    cached = _bq_cache.get(scope)
    if cached is not None and (time.time() - cached[1]) < _BQ_CACHE_TTL_SECONDS:
        return cached[0]

    raw_rules = None
    try:
        from google.cloud import bigquery

        client = bigquery.Client(project=os.getenv("GCP_PROJECT_ID", "amazon-ppc-bid-optimizer"))
        rows = list(
            client.query(
                f"SELECT config_json FROM `{_STACKING_RULES_TABLE}` WHERE scope = @scope LIMIT 1",
                job_config=bigquery.QueryJobConfig(
                    query_parameters=[bigquery.ScalarQueryParameter("scope", "STRING", scope)]
                ),
            ).result()
        )
        if rows:
            raw_rules = json.loads(rows[0].config_json)
    except Exception as exc:
        logger.warning(f"Failed to read stacking rules for scope '{scope}' from BigQuery, will fall back: {exc}")
        raw_rules = None

    _bq_cache[scope] = (raw_rules, time.time())
    return raw_rules


def save_rules_for_campaign(scope: str, raw_rules: List[Dict[str, Any]]) -> None:
    """Persist a rule set for a scope ('default' or a campaign_id). Replaces
    whatever was there for that scope. Raises on failure rather than
    swallowing it - unlike reads, a save the caller believes succeeded but
    silently didn't is worse than a visible error."""
    from google.cloud import bigquery

    client = bigquery.Client(project=os.getenv("GCP_PROJECT_ID", "amazon-ppc-bid-optimizer"))
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
    _bq_cache.pop(scope, None)


def load_rules_for_campaign(campaign_id: Any) -> List[Rule]:
    """Rules for a single campaign: a BigQuery row scoped to that campaign_id
    fully replaces the default rule set; campaigns with no row fall back to
    the 'default' scope's row, and if BigQuery has neither (unreachable, or
    nothing saved yet), fall back to the bundled JSON file so a bid-optimizer
    run never silently gets no rules due to a transient BigQuery issue."""
    raw_rules = _get_raw_rules_from_bigquery(str(campaign_id))
    if raw_rules is None:
        raw_rules = _get_raw_rules_from_bigquery("default")
    if raw_rules is None:
        json_config = _load_json_config()
        per_campaign = json_config.get("per_campaign", {})
        raw_rules = per_campaign.get(str(campaign_id), json_config.get("default", []))
    return _rules_from_list(raw_rules)
