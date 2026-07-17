"""Unit tests for the ACOS-tier campaign templates (Defensive/Core/High-LTV/Launch)."""
import pytest

from optimized_launch_preview import (
    CAMPAIGN_TEMPLATES,
    build_optimized_launch_preview,
    resolve_campaign_template,
)


def test_four_templates_exist():
    assert set(CAMPAIGN_TEMPLATES) == {"DEFENSIVE", "CORE", "HIGH_LTV", "LAUNCH"}


def test_no_template_falls_back_to_prior_defaults():
    resolved = resolve_campaign_template(None)
    assert resolved["template"] is None
    assert resolved["target_acos"] is None
    assert resolved["budget"] == 10.0
    assert resolved["fallback_bid"] == 0.75


def test_template_name_is_case_and_separator_insensitive():
    for name in ["defensive", "Defensive", "DEFENSIVE", "high-ltv", "High LTV", "HIGH_LTV"]:
        resolved = resolve_campaign_template(name)
        assert resolved["template"] in ("DEFENSIVE", "HIGH_LTV")


def test_unknown_template_raises_value_error():
    with pytest.raises(ValueError, match="Unknown campaign template"):
        resolve_campaign_template("not_a_real_template")


def test_explicit_budget_overrides_template_default():
    resolved = resolve_campaign_template("core", budget=25.0)
    assert resolved["budget"] == 25.0
    assert resolved["fallback_bid"] == CAMPAIGN_TEMPLATES["CORE"]["fallback_bid"]
    assert resolved["target_acos"] == CAMPAIGN_TEMPLATES["CORE"]["target_acos"]


def test_defensive_is_cheaper_and_tighter_than_high_ltv():
    defensive = resolve_campaign_template("defensive")
    high_ltv = resolve_campaign_template("high_ltv")
    assert defensive["target_acos"] < high_ltv["target_acos"]
    assert defensive["budget"] < high_ltv["budget"]


def test_preview_includes_template_settings():
    preview = build_optimized_launch_preview(
        product={"title": "Living Compost 5lb", "asin": "B000TEST", "sku": "SKU-1"},
        template="launch",
    )
    assert preview["settings"]["template"] == "LAUNCH"
    assert preview["settings"]["template_label"] == "Launch"
    assert preview["settings"]["target_acos"] == CAMPAIGN_TEMPLATES["LAUNCH"]["target_acos"]
    assert preview["settings"]["daily_budget_total"] > 0
    assert any("Target ACOS" in item for item in preview["review_checklist"])


def test_preview_without_template_has_no_template_metadata():
    preview = build_optimized_launch_preview(
        product={"title": "Living Compost 5lb", "asin": "B000TEST", "sku": "SKU-1"},
    )
    assert preview["settings"]["template"] is None
    assert preview["settings"]["target_acos"] is None
    assert not any("Target ACOS" in item for item in preview["review_checklist"])


def test_preview_raises_on_unknown_template():
    with pytest.raises(ValueError):
        build_optimized_launch_preview(
            product={"title": "Living Compost 5lb", "asin": "B000TEST", "sku": "SKU-1"},
            template="not_a_real_template",
        )


def test_preview_still_side_effect_free_with_template():
    preview = build_optimized_launch_preview(
        product={"title": "Living Compost 5lb", "asin": "B000TEST", "sku": "SKU-1"},
        template="high_ltv",
    )
    assert preview["dry_run"] is True
