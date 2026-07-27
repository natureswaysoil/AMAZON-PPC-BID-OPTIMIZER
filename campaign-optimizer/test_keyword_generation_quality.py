from optimize_campaigns import generate_keywords_for_product


def test_soil_booster_uses_buyer_intent_not_title_fragments():
    keywords = generate_keywords_for_product({
        "Title": (
            "Nature's Way Soil Booster and Loosener Organic Formula to "
            "Enhance Soil Health Improve Aeration and Promote Root Growth"
        ),
        "Category": "Garden",
    })

    assert "soil booster" in keywords
    assert "liquid soil conditioner" in keywords
    assert "compacted soil treatment" in keywords
    assert "organic formula" not in keywords
    assert "formula enhance" not in keywords
    assert "health improve" not in keywords


def test_explicit_research_keywords_still_take_priority():
    keywords = generate_keywords_for_product({
        "Title": "Nature's Way Soil Organic Tomato Liquid Fertilizer",
        "Keywords": "calcium tomato fertilizer",
        "Research_Keywords": "tomato plant food",
        "Category": "Fertilizer",
    })

    assert keywords[:2] == ["calcium tomato fertilizer", "tomato plant food"]
    assert "tomato fertilizer" in keywords
