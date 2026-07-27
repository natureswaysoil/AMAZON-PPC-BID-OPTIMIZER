from optimize_campaigns import AmazonAdsClient


def test_list_ad_groups_filters_campaign_and_paginates():
    client = object.__new__(AmazonAdsClient)
    responses = iter([
        {
            "adGroups": [
                {"campaignId": "123", "adGroupId": "a", "defaultBid": 0.75},
                {"campaignId": "wrong", "adGroupId": "x", "defaultBid": 9.99},
            ],
            "nextToken": "next",
        },
        {
            "adGroups": [
                {"campaignId": "123", "adGroupId": "b", "defaultBid": 0.85},
            ],
        },
    ])
    client.post = lambda *args, **kwargs: next(responses)

    groups = client.list_ad_groups("123")

    assert [group["adGroupId"] for group in groups] == ["a", "b"]


def test_auto_bid_recommendation_uses_amazon_returned_range():
    client = object.__new__(AmazonAdsClient)
    captured = {}

    def fake_post(endpoint, body, **kwargs):
        captured["endpoint"] = endpoint
        captured["body"] = body
        return {
            "bidRecommendations": [{
                "bidRecommendationsForTargetingExpressions": [
                    {"bidValues": [{"suggestedBid": 0.62}, {"suggestedBid": 1.14}]},
                    {"bidValues": [{"suggestedBid": 0.91}]},
                ],
            }],
        }

    client.post = fake_post

    recommendation = client.get_auto_bid_recommendation("123", "456")

    assert captured["endpoint"] == "/sp/targets/bid/recommendations"
    assert {item["type"] for item in captured["body"]["targetingExpressions"]} == {
        "CLOSE_MATCH",
        "LOOSE_MATCH",
        "SUBSTITUTES",
        "COMPLEMENTS",
    }
    assert recommendation == {"low": 0.62, "high": 1.14, "suggested": 0.91}
