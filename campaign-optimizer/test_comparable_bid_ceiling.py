import budget_dayparting


def test_prime_bid_uses_comparable_high_as_ceiling(monkeypatch):
    monkeypatch.setattr(budget_dayparting, "get_budget_protection_mode", lambda: "PRIME")

    low, high, applied = budget_dayparting.choose_budget_protected_bid(
        {"low": 2.49, "high": 4.14, "suggested": 3.32},
        fallback=0.75,
    )

    assert (low, high, applied) == (2.49, 4.14, 4.14)


def test_lower_cost_product_cannot_exceed_its_comparable_high(monkeypatch):
    monkeypatch.setattr(budget_dayparting, "get_budget_protection_mode", lambda: "PRIME")

    _, high, applied = budget_dayparting.choose_budget_protected_bid(
        {"low": 0.49, "high": 1.20, "suggested": 0.85},
        fallback=5.00,
    )

    assert high == 1.20
    assert applied <= high
