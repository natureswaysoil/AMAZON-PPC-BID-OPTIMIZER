"""Unit tests for preview_server.py's HTTP wrapper around
AOVBidOptimizer.preview_optimization()."""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import os
os.environ["DAILY_OPTIMIZER_TOKEN"] = "test-token"

from fastapi.testclient import TestClient

import preview_server
from core.rule_engine import Rule

client = TestClient(preview_server.app)
AUTH_HEADERS = {"X-Daily-Optimizer-Token": "test-token"}


def test_health_needs_no_auth():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_preview_rejects_missing_token():
    response = client.post("/preview", json={})
    assert response.status_code == 401


def test_preview_rejects_wrong_token():
    response = client.post("/preview", json={}, headers={"X-Daily-Optimizer-Token": "wrong"})
    assert response.status_code == 403


def test_preview_accepts_bearer_token():
    fake_summary = {"dry_run": True, "keywords_evaluated": 0}
    with patch.object(preview_server.AOVBidOptimizer, "preview_optimization", return_value=fake_summary):
        response = client.post("/preview", json={}, headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 200
    assert response.json() == fake_summary


def test_preview_passes_target_acos_override_through():
    captured = {}

    def fake_preview(self, target_acos_override=None, rules_override=None):
        captured["target_acos_override"] = target_acos_override
        captured["rules_override"] = rules_override
        return {"dry_run": True}

    with patch.object(preview_server.AOVBidOptimizer, "preview_optimization", fake_preview):
        response = client.post("/preview", json={"target_acos": 0.18}, headers=AUTH_HEADERS)

    assert response.status_code == 200
    assert captured["target_acos_override"] == 0.18
    assert captured["rules_override"] is None


def test_preview_converts_rules_payload_to_rule_objects():
    captured = {}

    def fake_preview(self, target_acos_override=None, rules_override=None):
        captured["rules_override"] = rules_override
        return {"dry_run": True}

    payload = {
        "rules": [
            {"type": "spend_cap_pause", "enabled": True, "params": {"max_cost_30d": 20}},
        ]
    }
    with patch.object(preview_server.AOVBidOptimizer, "preview_optimization", fake_preview):
        response = client.post("/preview", json=payload, headers=AUTH_HEADERS)

    assert response.status_code == 200
    rules = captured["rules_override"]
    assert len(rules) == 1
    assert isinstance(rules[0], Rule)
    assert rules[0].type == "spend_cap_pause"
    assert rules[0].params == {"max_cost_30d": 20}


def test_preview_returns_502_on_internal_failure():
    def fake_preview(self, target_acos_override=None, rules_override=None):
        raise RuntimeError("BigQuery unreachable")

    with patch.object(preview_server.AOVBidOptimizer, "preview_optimization", fake_preview):
        response = client.post("/preview", json={}, headers=AUTH_HEADERS)

    assert response.status_code == 502
    assert response.json()["error"] is True
