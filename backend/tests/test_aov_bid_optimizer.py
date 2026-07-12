"""Unit tests for bid-safety decisions."""
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from jobs.optimization.aov_bid_optimizer import AOVBidOptimizer
from core.config import settings


@pytest.fixture
def optimizer():
    return AOVBidOptimizer()


def keyword(**overrides):
    data = {
        "aov": 30.0,
        "match_type": "EXACT",
        "current_bid": 1.00,
        "clicks_30d": 0,
        "conversions_30d": 0,
        "cost_30d": 0.0,
        "acos": 0.0,
        "cvr": 0.0,
        "target_acos": 0.30,
    }
    data.update(overrides)
    return data


def test_zero_sales_with_insufficient_data_does_not_increase(optimizer):
    result = optimizer.calculate_optimal_bid(
        keyword(clicks_30d=5, cost_30d=4.50), current_hour=12
    )
    assert result["new_bid"] == 1.00
    assert result["decision"] == "insufficient_zero_order_data"


def test_zero_sales_loss_gate_reduces_bid(optimizer):
    result = optimizer.calculate_optimal_bid(
        keyword(clicks_30d=settings.LOSE_CLICKS_MIN, cost_30d=9.00),
        current_hour=12,
    )
    assert result["new_bid"] == 0.85
    assert result["decision"] == "zero_order_loss_gate"
    assert result["pause_recommended"] is False


def test_zero_sales_pause_gate_uses_max_down_rail(optimizer):
    result = optimizer.calculate_optimal_bid(
        keyword(
            clicks_30d=settings.PAUSE_CLICKS_MIN,
            cost_30d=settings.PAUSE_SPEND_MIN,
        ),
        current_hour=12,
    )
    assert result["new_bid"] == round(1.00 * (1 - settings.MAX_DOWN_PCT_PER_RUN), 2)
    assert result["decision"] == "zero_order_pause_gate"
    assert result["pause_recommended"] is True


def test_tier_e_is_reachable(optimizer):
    tier = optimizer.get_performance_tier(
        keyword(clicks_30d=51, conversions_30d=0)
    )
    assert tier == "E"


@pytest.mark.parametrize(
    "aov,expected",
    [
        (29.99, "L"),
        (30.00, "M"),
        (45.99, "M"),
        (46.00, "H"),
        (69.99, "H"),
        (70.00, "X"),
        (1200.00, "X"),
    ],
)
def test_aov_boundaries_use_exclusive_upper_limits(optimizer, aov, expected):
    assert optimizer.get_aov_tier(aov) == expected


def test_profitable_keyword_can_increase_but_not_above_run_limit(optimizer):
    result = optimizer.calculate_optimal_bid(
        keyword(
            aov=100.0,
            current_bid=1.00,
            clicks_30d=30,
            conversions_30d=6,
            cost_30d=12.00,
            acos=0.15,
            cvr=0.20,
        ),
        current_hour=17,
    )
    assert result["new_bid"] <= round(1.00 * (1 + settings.MAX_UP_PCT_PER_RUN), 2)
    assert result["new_bid"] > 1.00


def test_bad_acos_cannot_drop_more_than_run_limit(optimizer):
    result = optimizer.calculate_optimal_bid(
        keyword(
            current_bid=2.00,
            clicks_30d=40,
            conversions_30d=2,
            cost_30d=60.00,
            acos=1.00,
            cvr=0.05,
        ),
        current_hour=12,
    )
    assert result["new_bid"] >= round(2.00 * (1 - settings.MAX_DOWN_PCT_PER_RUN), 2)


def test_global_minimum_bid_is_enforced(optimizer):
    result = optimizer.calculate_optimal_bid(
        keyword(
            current_bid=settings.MIN_BID,
            clicks_30d=settings.PAUSE_CLICKS_MIN,
            cost_30d=settings.PAUSE_SPEND_MIN,
        ),
        current_hour=12,
    )
    assert result["new_bid"] == settings.MIN_BID


def test_global_maximum_bid_is_enforced(optimizer):
    result = optimizer.calculate_optimal_bid(
        keyword(
            aov=500.0,
            current_bid=settings.MAX_BID,
            clicks_30d=50,
            conversions_30d=10,
            cost_30d=20.00,
            acos=0.10,
            cvr=0.20,
        ),
        current_hour=17,
    )
    assert result["new_bid"] <= settings.MAX_BID
