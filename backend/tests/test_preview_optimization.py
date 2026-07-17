"""Unit tests for the read-only preview/what-if path: evaluate_keywords,
preview_optimization, and summarize_preview. These must never touch
BigQuery writes or the Amazon Ads API - each test that exercises
preview_optimization asserts that explicitly."""
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from jobs.optimization.aov_bid_optimizer import AOVBidOptimizer, summarize_preview
from core.rule_engine import Rule


def keyword_row(**overrides):
    row = {
        "keyword_id": 1,
        "keyword_text": "test keyword",
        "current_bid": 1.00,
        "match_type": "EXACT",
        "campaign_id": "111",
        "clicks_30d": 30,
        "conversions_30d": 6,
        "cost_30d": 12.0,
        "sales_30d": 80.0,
        "cvr": 0.20,
        "acos": 0.15,
    }
    row.update(overrides)
    return row


@pytest.fixture
def optimizer():
    return AOVBidOptimizer()


def test_evaluate_keywords_uses_target_acos_override(optimizer):
    # acos=0.15 sits comfortably below a 0.30 target (increase band) but
    # above a stricter 0.10 target (decrease band) - proves the override,
    # not the row's own data, drives the decision.
    optimizations = optimizer.evaluate_keywords(
        [keyword_row()],
        current_hour=17,
        current_weekday=2,
        target_acos=0.10,
        rules_resolver=lambda campaign_id: [],
    )
    assert optimizations
    assert optimizations[0]["new_bid"] < 1.00
    assert "Target: 10.0%" in optimizations[0]["reasoning"]


def test_evaluate_keywords_applies_rules_resolver_override(optimizer):
    rules = [Rule(type="spend_cap_pause", enabled=True, params={"max_cost_30d": 1.0})]
    optimizations = optimizer.evaluate_keywords(
        [keyword_row(cost_30d=999)],
        current_hour=17,
        current_weekday=2,
        target_acos=0.30,
        rules_resolver=lambda campaign_id: rules,
    )
    assert optimizations
    assert optimizations[0]["pause_recommended"] is True


def test_evaluate_keywords_drops_unchanged_bids(optimizer):
    # acos (20%) sits in the "hold" band relative to a 16% target and the
    # tier-A ceiling has headroom above current_bid, so nothing should move.
    optimizations = optimizer.evaluate_keywords(
        [keyword_row(acos=0.20)],
        current_hour=17,
        current_weekday=2,
        target_acos=0.16,
        rules_resolver=lambda campaign_id: [],
    )
    assert optimizations == []


def test_preview_optimization_never_logs_to_bigquery(optimizer, monkeypatch):
    monkeypatch.setattr(optimizer, "fetch_keyword_performance_rows", lambda: [keyword_row()])

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("preview_optimization must not write optimizations to BigQuery")

    monkeypatch.setattr(optimizer, "_log_optimizations", _fail_if_called)

    summary = optimizer.preview_optimization(target_acos_override=0.15)
    assert summary["dry_run"] is True
    assert summary["keywords_evaluated"] == 1


def test_preview_optimization_respects_rules_override(optimizer, monkeypatch):
    monkeypatch.setattr(optimizer, "fetch_keyword_performance_rows", lambda: [keyword_row(cost_30d=999)])
    monkeypatch.setattr(optimizer, "_log_optimizations", lambda *a, **k: None)

    rules_override = [Rule(type="spend_cap_pause", enabled=True, params={"max_cost_30d": 1.0})]
    summary = optimizer.preview_optimization(target_acos_override=0.30, rules_override=rules_override)

    assert summary["keywords_projected_to_pause"] == 1
    assert summary["keywords_with_projected_changes"] == 1


def test_preview_optimization_reports_no_changes_cleanly(optimizer, monkeypatch):
    monkeypatch.setattr(
        optimizer, "fetch_keyword_performance_rows",
        lambda: [keyword_row(acos=0.20)],
    )
    monkeypatch.setattr(optimizer, "_log_optimizations", lambda *a, **k: None)

    summary = optimizer.preview_optimization(target_acos_override=0.16)
    assert summary["keywords_evaluated"] == 1
    assert summary["keywords_with_projected_changes"] == 0
    assert summary["sample_changes"] == []


def test_summarize_preview_computes_totals_and_sample():
    rows = [{}, {}, {}]
    optimizations = [
        {"keyword_id": 1, "keyword_text": "a", "campaign_id": "1", "current_bid": 1.00, "new_bid": 1.20,
         "pause_recommended": False, "reasoning": "up"},
        {"keyword_id": 2, "keyword_text": "b", "campaign_id": "1", "current_bid": 2.00, "new_bid": 1.50,
         "pause_recommended": False, "reasoning": "down"},
        {"keyword_id": 3, "keyword_text": "c", "campaign_id": "1", "current_bid": 1.00, "new_bid": 0.35,
         "pause_recommended": True, "reasoning": "paused"},
    ]
    summary = summarize_preview(rows, optimizations)

    assert summary["keywords_evaluated"] == 3
    assert summary["keywords_with_projected_changes"] == 3
    assert summary["keywords_projected_to_increase"] == 1
    assert summary["keywords_projected_to_decrease"] == 1
    assert summary["keywords_projected_to_pause"] == 1
    assert summary["current_bid_total"] == 4.00
    assert summary["projected_bid_total"] == 3.05
    assert summary["projected_bid_delta"] == round(3.05 - 4.00, 2)
    assert len(summary["sample_changes"]) == 3
