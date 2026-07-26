from unittest.mock import MagicMock

import optimize_campaigns as optimizer


def test_get_bid_recommendation_uses_theme_based_v3_endpoint():
    client = optimizer.AmazonAdsClient.__new__(optimizer.AmazonAdsClient)
    client.post = MagicMock(return_value={
        "bidRecommendations": [{
            "theme": "CONVERSION_OPPORTUNITIES",
            "bidRecommendationsForTargetingExpressions": [{
                "targetingExpression": {
                    "type": "KEYWORD_EXACT_MATCH",
                    "value": "tomato fertilizer",
                },
                "bidValues": [
                    {"suggestedBid": 1.24},
                    {"suggestedBid": 1.62},
                    {"suggestedBid": 1.94},
                ],
            }],
        }],
    })

    result = client.get_bid_recommendation(
        campaign_id="98164985993008",
        ad_group_id="229992475561700",
        keyword="tomato fertilizer",
        match_type="EXACT",
    )

    assert result == {"low": 1.24, "high": 1.94, "suggested": 1.62}
    media_type = "application/vnd.spthemebasedbidrecommendation.v3+json"
    client.post.assert_called_once_with(
        "/sp/targets/bid/recommendations",
        {
            "recommendationType": "BIDS_FOR_EXISTING_AD_GROUP",
            "campaignId": "98164985993008",
            "adGroupId": "229992475561700",
            "targetingExpressions": [{
                "type": "KEYWORD_EXACT_MATCH",
                "value": "tomato fertilizer",
            }],
        },
        content_type=media_type,
        accept=media_type,
    )


def test_get_bid_recommendation_returns_empty_when_amazon_has_no_values():
    client = optimizer.AmazonAdsClient.__new__(optimizer.AmazonAdsClient)
    client.post = MagicMock(return_value={"bidRecommendations": []})

    assert client.get_bid_recommendation("1", "2", "tomato fertilizer") == {}
