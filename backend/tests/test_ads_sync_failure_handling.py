import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from jobs.data_sync.amazon_ads_sync import AmazonAdsSync


def test_error_details_includes_amazon_response_body():
    response = Mock(status_code=400, text='{"code":"INVALID_ARGUMENT","details":"bad column"}')
    exc = RuntimeError("request failed")
    exc.response = response

    details = AmazonAdsSync._error_details(exc)

    assert "HTTP 400" in details
    assert "INVALID_ARGUMENT" in details
    assert "bad column" in details


def test_run_raises_when_every_report_fails():
    sync = AmazonAdsSync.__new__(AmazonAdsSync)
    sync.amazon_client = Mock(region="NA", base_url="https://advertising-api.amazon.com")
    sync.dataset = "amazon_ppc"

    failure = RuntimeError("report rejected")
    sync.sync_keywords_performance = Mock(side_effect=failure)
    sync.sync_campaign_performance = Mock(side_effect=failure)
    sync.sync_advertised_product_metrics = Mock(side_effect=failure)
    sync.sync_search_terms = Mock(side_effect=failure)

    with pytest.raises(RuntimeError, match="All Amazon Ads report syncs failed"):
        sync.run()


def test_run_succeeds_when_at_least_one_report_succeeds():
    sync = AmazonAdsSync.__new__(AmazonAdsSync)
    sync.amazon_client = Mock(region="NA", base_url="https://advertising-api.amazon.com")
    sync.dataset = "amazon_ppc"

    sync.sync_keywords_performance = Mock(return_value=[{"keyword_id": 1}])
    sync.sync_campaign_performance = Mock(side_effect=RuntimeError("report rejected"))
    sync.sync_advertised_product_metrics = Mock(side_effect=RuntimeError("report rejected"))
    sync.sync_search_terms = Mock(side_effect=RuntimeError("report rejected"))

    sync.run()
