"""Unit tests for stacking_rules_store.py (the BigQuery-backed config store
consumed by the /api/stacking-rules endpoints)."""
import pytest

from stacking_rules_store import (
    InvalidRuleError,
    RULE_TYPE_METADATA,
    get_rules,
    save_rules,
    validate_rules,
)


def test_rule_type_metadata_matches_backend_rule_engine():
    """Keep this file's registry in sync with backend/core/rule_engine.py's -
    these are duplicated by necessity (separate Docker contexts) but must
    describe the same four rule types or the UI and the evaluator disagree."""
    assert set(RULE_TYPE_METADATA) == {
        "spend_cap_pause", "off_peak_bid_reduction", "weekend_bid_adjustment", "inventory_days_pause",
    }


def test_validate_rules_accepts_known_types():
    validate_rules([{"type": "spend_cap_pause", "enabled": True, "params": {"max_cost_30d": 10}}])


def test_validate_rules_rejects_unknown_type():
    with pytest.raises(InvalidRuleError, match="Unknown rule type"):
        validate_rules([{"type": "not_a_real_rule"}])


def test_validate_rules_rejects_non_list():
    with pytest.raises(InvalidRuleError, match="must be a list"):
        validate_rules({"type": "spend_cap_pause"})


def test_validate_rules_rejects_missing_type_field():
    with pytest.raises(InvalidRuleError, match="'type' field"):
        validate_rules([{"enabled": True}])


def test_get_rules_returns_empty_list_when_no_row(monkeypatch):
    from google.cloud import bigquery as real_bigquery

    class _EmptyResult:
        def result(self):
            return []

    class _FakeClient:
        def __init__(self, *a, **k):
            pass

        def query(self, sql, job_config=None):
            return _EmptyResult()

    monkeypatch.setattr(real_bigquery, "Client", _FakeClient)
    assert get_rules("nonexistent-scope") == []


def test_get_rules_returns_empty_list_on_query_failure(monkeypatch):
    from google.cloud import bigquery as real_bigquery

    class _FailingClient:
        def __init__(self, *a, **k):
            raise RuntimeError("no credentials")

    monkeypatch.setattr(real_bigquery, "Client", _FailingClient)
    assert get_rules("some-scope") == []


def test_save_rules_rejects_invalid_rules_before_any_bigquery_call(monkeypatch):
    from google.cloud import bigquery as real_bigquery

    def _fail_if_called(*a, **k):
        raise AssertionError("save_rules must validate before touching BigQuery")

    monkeypatch.setattr(real_bigquery, "Client", _fail_if_called)

    with pytest.raises(InvalidRuleError):
        save_rules("default", [{"type": "not_a_real_rule"}])


def test_save_rules_runs_merge_query(monkeypatch):
    from google.cloud import bigquery as real_bigquery

    executed = {}

    class _FakeResult:
        def result(self):
            return None

    class _FakeClient:
        def __init__(self, *a, **k):
            pass

        def query(self, sql, job_config=None):
            executed["sql"] = sql
            return _FakeResult()

    monkeypatch.setattr(real_bigquery, "Client", _FakeClient)

    save_rules("default", [{"type": "spend_cap_pause", "enabled": True, "params": {"max_cost_30d": 25}}])
    assert "MERGE" in executed["sql"]
