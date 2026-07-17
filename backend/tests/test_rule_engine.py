"""Unit tests for the stackable rule engine."""
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.rule_engine import Rule, apply_stacked_rules, load_rules_for_campaign, save_rules_for_campaign


def base_decision(**overrides):
    decision = {
        "new_bid": 1.00,
        "pause_recommended": False,
        "reasoning": "base decision",
    }
    decision.update(overrides)
    return decision


def test_disabled_rule_is_a_no_op():
    rules = [Rule(type="spend_cap_pause", enabled=False, params={"max_cost_30d": 10.0})]
    decision = apply_stacked_rules(base_decision(), {"cost_30d": 999}, rules, min_bid=0.35)
    assert decision["new_bid"] == 1.00
    assert decision["pause_recommended"] is False


def test_spend_cap_pause_fires_over_cap():
    rules = [Rule(type="spend_cap_pause", enabled=True, params={"max_cost_30d": 10.0})]
    decision = apply_stacked_rules(base_decision(), {"cost_30d": 15.0}, rules, min_bid=0.35)
    assert decision["new_bid"] == 0.35
    assert decision["pause_recommended"] is True
    assert "spend_cap_pause" in decision["reasoning"]


def test_spend_cap_pause_does_not_fire_under_cap():
    rules = [Rule(type="spend_cap_pause", enabled=True, params={"max_cost_30d": 10.0})]
    decision = apply_stacked_rules(base_decision(), {"cost_30d": 5.0}, rules, min_bid=0.35)
    assert decision["new_bid"] == 1.00
    assert decision["pause_recommended"] is False


def test_inventory_days_pause_fires_below_floor():
    rules = [Rule(type="inventory_days_pause", enabled=True, params={"min_days": 15})]
    decision = apply_stacked_rules(base_decision(), {"inventory_days_supply": 5}, rules, min_bid=0.35)
    assert decision["new_bid"] == 0.35
    assert decision["pause_recommended"] is True


def test_inventory_days_pause_is_a_no_op_without_inventory_data():
    rules = [Rule(type="inventory_days_pause", enabled=True, params={"min_days": 15})]
    decision = apply_stacked_rules(base_decision(), {}, rules, min_bid=0.35)
    assert decision["new_bid"] == 1.00
    assert decision["pause_recommended"] is False


def test_off_peak_bid_reduction_applies_outside_peak_hours():
    rules = [Rule(
        type="off_peak_bid_reduction",
        enabled=True,
        params={"reduction_pct": 0.10, "peak_hours": [[16, 18]]},
    )]
    decision = apply_stacked_rules(base_decision(), {}, rules, hour=9, min_bid=0.35)
    assert decision["new_bid"] == 0.90


def test_off_peak_bid_reduction_skips_inside_peak_hours():
    rules = [Rule(
        type="off_peak_bid_reduction",
        enabled=True,
        params={"reduction_pct": 0.10, "peak_hours": [[16, 18]]},
    )]
    decision = apply_stacked_rules(base_decision(), {}, rules, hour=16, min_bid=0.35)
    assert decision["new_bid"] == 1.00


def test_weekend_bid_adjustment_applies_on_saturday():
    rules = [Rule(type="weekend_bid_adjustment", enabled=True, params={"adjustment_pct": -0.15})]
    decision = apply_stacked_rules(base_decision(), {}, rules, weekday=5, min_bid=0.35)
    assert decision["new_bid"] == 0.85


def test_weekend_bid_adjustment_skips_weekday():
    rules = [Rule(type="weekend_bid_adjustment", enabled=True, params={"adjustment_pct": -0.15})]
    decision = apply_stacked_rules(base_decision(), {}, rules, weekday=2, min_bid=0.35)
    assert decision["new_bid"] == 1.00


def test_rules_stack_in_order():
    rules = [
        Rule(type="off_peak_bid_reduction", enabled=True, params={"reduction_pct": 0.10, "peak_hours": []}),
        Rule(type="weekend_bid_adjustment", enabled=True, params={"adjustment_pct": -0.10}),
    ]
    decision = apply_stacked_rules(base_decision(), {}, rules, hour=9, weekday=6, min_bid=0.35)
    assert decision["new_bid"] == round(1.00 * 0.90 * 0.90, 2)


def test_pause_short_circuits_later_bid_adjustments():
    rules = [
        Rule(type="spend_cap_pause", enabled=True, params={"max_cost_30d": 1.0}),
        Rule(type="off_peak_bid_reduction", enabled=True, params={"reduction_pct": 0.50, "peak_hours": []}),
    ]
    decision = apply_stacked_rules(base_decision(), {"cost_30d": 999}, rules, hour=9, min_bid=0.35)
    assert decision["new_bid"] == 0.35
    assert decision["pause_recommended"] is True


def test_global_min_and_max_are_enforced_after_stacking():
    rules = [Rule(type="off_peak_bid_reduction", enabled=True, params={"reduction_pct": 0.99, "peak_hours": []})]
    decision = apply_stacked_rules(base_decision(new_bid=0.50), {}, rules, hour=9, min_bid=0.35, max_bid=7.0)
    assert decision["new_bid"] == 0.35


def test_unknown_rule_type_is_skipped_without_raising():
    rules = [Rule(type="not_a_real_rule", enabled=True, params={})]
    decision = apply_stacked_rules(base_decision(), {}, rules, min_bid=0.35)
    assert decision["new_bid"] == 1.00


def test_load_rules_for_campaign_falls_back_to_json_when_bigquery_has_nothing(tmp_path, monkeypatch):
    import core.rule_engine as rule_engine

    config_path = tmp_path / "stacking_rules.json"
    config_path.write_text(
        '{"default": [{"type": "spend_cap_pause", "enabled": true, "params": {"max_cost_30d": 5}}], '
        '"per_campaign": {"999": [{"type": "weekend_bid_adjustment", "enabled": true, "params": {}}]}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(rule_engine, "CONFIG_PATH", config_path)
    monkeypatch.setattr(rule_engine, "_get_raw_rules_from_bigquery", lambda scope: None)

    default_rules = rule_engine.load_rules_for_campaign("123")
    assert len(default_rules) == 1
    assert default_rules[0].type == "spend_cap_pause"

    campaign_rules = rule_engine.load_rules_for_campaign("999")
    assert len(campaign_rules) == 1
    assert campaign_rules[0].type == "weekend_bid_adjustment"


def test_load_rules_for_campaign_missing_config_file_returns_empty(tmp_path, monkeypatch):
    import core.rule_engine as rule_engine

    monkeypatch.setattr(rule_engine, "CONFIG_PATH", tmp_path / "does_not_exist.json")
    monkeypatch.setattr(rule_engine, "_get_raw_rules_from_bigquery", lambda scope: None)
    assert rule_engine.load_rules_for_campaign("123") == []


def test_load_rules_for_campaign_prefers_bigquery_campaign_scope(monkeypatch):
    import core.rule_engine as rule_engine

    def fake_bq(scope):
        if scope == "555":
            return [{"type": "spend_cap_pause", "enabled": True, "params": {"max_cost_30d": 9}}]
        return [{"type": "weekend_bid_adjustment", "enabled": True, "params": {}}]  # "default" scope

    monkeypatch.setattr(rule_engine, "_get_raw_rules_from_bigquery", fake_bq)

    campaign_rules = rule_engine.load_rules_for_campaign("555")
    assert len(campaign_rules) == 1
    assert campaign_rules[0].type == "spend_cap_pause"


def test_load_rules_for_campaign_falls_back_to_bigquery_default_scope(monkeypatch):
    import core.rule_engine as rule_engine

    def fake_bq(scope):
        if scope == "default":
            return [{"type": "weekend_bid_adjustment", "enabled": True, "params": {}}]
        return None  # no row for this specific campaign

    monkeypatch.setattr(rule_engine, "_get_raw_rules_from_bigquery", fake_bq)

    campaign_rules = rule_engine.load_rules_for_campaign("777")
    assert len(campaign_rules) == 1
    assert campaign_rules[0].type == "weekend_bid_adjustment"


def test_get_raw_rules_from_bigquery_caches_and_falls_back_on_error(monkeypatch):
    import core.rule_engine as rule_engine
    from google.cloud import bigquery as real_bigquery

    rule_engine._bq_cache.clear()

    class _FailingClient:
        def __init__(self, *a, **k):
            raise RuntimeError("no credentials in this environment")

    monkeypatch.setattr(real_bigquery, "Client", _FailingClient)

    result = rule_engine._get_raw_rules_from_bigquery("some-scope")
    assert result is None
    # Cached even on failure, so a flaky/unreachable BigQuery doesn't retry on every keyword.
    assert "some-scope" in rule_engine._bq_cache


def test_save_rules_for_campaign_runs_merge_and_clears_cache(monkeypatch):
    import core.rule_engine as rule_engine
    from google.cloud import bigquery as real_bigquery

    rule_engine._bq_cache["default"] = ([{"type": "spend_cap_pause", "enabled": False, "params": {}}], 0)

    executed = {}

    class _FakeResult:
        def result(self):
            return None

    class _FakeClient:
        def __init__(self, *a, **k):
            pass

        def query(self, sql, job_config=None):
            executed["sql"] = sql
            executed["job_config"] = job_config
            return _FakeResult()

    monkeypatch.setattr(real_bigquery, "Client", _FakeClient)

    new_rules = [{"type": "weekend_bid_adjustment", "enabled": True, "params": {"adjustment_pct": -0.1}}]
    rule_engine.save_rules_for_campaign("default", new_rules)

    assert "MERGE" in executed["sql"]
    assert "default" not in rule_engine._bq_cache
