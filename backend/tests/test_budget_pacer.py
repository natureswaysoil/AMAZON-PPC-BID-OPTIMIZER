from datetime import date, timedelta
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from jobs.optimization.budget_pacer import proposed_budget


def test_missing_or_zero_performance_never_increases_budget():
    today = date.today()
    assert proposed_budget(10, None, None, None, .25) is None
    assert proposed_budget(10, 0, 0, today, .25) is None
    assert proposed_budget(10, 5, 0, today, .25) is None


def test_stale_performance_never_increases_budget():
    assert proposed_budget(10, 5, 100, date.today() - timedelta(days=3), .25) is None


def test_above_target_acos_never_increases_budget():
    assert proposed_budget(10, 50, 100, date.today(), .25) is None


def test_fresh_profitable_underpaced_campaign_increases_ten_percent():
    assert proposed_budget(10, 20, 100, date.today(), .25) == 11.0
