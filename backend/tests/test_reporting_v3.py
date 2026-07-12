import gzip
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import requests

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from jobs.data_sync.amazon_ads_sync import AmazonAdsSync
from shared.reporting_v3 import _duplicate_report_id, request_and_download_report_v3


def test_duplicate_report_id_is_extracted_from_425_response():
    response = Mock(status_code=425)
    response.json.return_value = {
        "detail": "The Request is a duplicate of : 629d03ca-e4af-4989-99f6-382550f74481"
    }
    exc = requests.HTTPError(response=response)

    assert _duplicate_report_id(exc) == "629d03ca-e4af-4989-99f6-382550f74481"


def test_duplicate_report_is_polled_and_downloaded():
    duplicate_response = Mock(status_code=425)
    duplicate_response.json.return_value = {
        "detail": "The Request is a duplicate of : 629d03ca-e4af-4989-99f6-382550f74481"
    }
    duplicate_error = requests.HTTPError(response=duplicate_response)

    client = Mock()
    client._make_request.side_effect = [
        duplicate_error,
        {
            "status": "SUCCESS",
            "url": "https://example.s3.amazonaws.com/report.gz",
        },
    ]
    download = Mock(content=gzip.compress(b'{"campaignId":"1"}\n'))
    download.raise_for_status.return_value = None

    with patch("shared.reporting_v3.requests.get", return_value=download):
        rows = request_and_download_report_v3(client, {"name": "test"})

    assert rows == [{"campaignId": "1"}]
    first_call = client._make_request.call_args_list[0]
    assert first_call.kwargs["max_retries"] == 1


def test_transient_poll_error_is_retried():
    client = Mock()
    client._make_request.side_effect = [
        {"reportId": "629d03ca-e4af-4989-99f6-382550f74481"},
        requests.ConnectionError("temporary network failure"),
        {
            "status": "SUCCESS",
            "url": "https://example.s3.amazonaws.com/report.gz",
        },
    ]
    download = Mock(content=gzip.compress(b'{"campaignId":"1"}\n'))
    download.raise_for_status.return_value = None

    with (
        patch("shared.reporting_v3.time.sleep"),
        patch("shared.reporting_v3.requests.get", return_value=download),
    ):
        rows = request_and_download_report_v3(client, {"name": "test"})

    assert rows == [{"campaignId": "1"}]
    assert client._make_request.call_count == 3


def test_report_payloads_use_amazon_returned_field_names():
    sync = AmazonAdsSync.__new__(AmazonAdsSync)
    sync.amazon_client = Mock(region="NA", base_url="https://advertising-api.amazon.com")
    sync.dataset = "amazon_ppc"
    sync._load_to_bigquery = Mock()

    captured = []

    def capture(config):
        captured.append(config)
        return []

    sync._request_report = capture

    sync.sync_keywords_performance()
    sync.sync_campaign_performance()
    sync.sync_advertised_product_metrics()

    keyword_config = captured[0]["configuration"]
    campaign_config = captured[1]["configuration"]
    product_config = captured[2]["configuration"]

    assert keyword_config["reportTypeId"] == "spTargeting"
    assert keyword_config["groupBy"] == ["targeting"]
    assert "keyword" in keyword_config["columns"]
    assert "keywordText" not in keyword_config["columns"]

    assert "campaignBudgetAmount" in campaign_config["columns"]
    assert "campaignBudget" not in campaign_config["columns"]

    assert "advertisedAsin" in product_config["columns"]
    assert "advertisedSku" in product_config["columns"]
    assert "unitsSoldClicks14d" in product_config["columns"]
    assert "asin" not in product_config["columns"]
    assert "sku" not in product_config["columns"]


def test_transforms_accept_corrected_field_names():
    sync = AmazonAdsSync.__new__(AmazonAdsSync)

    campaign = sync._transform_campaign_data([
        {
            "campaignId": "1",
            "campaignBudgetAmount": "25.00",
            "sales14d": "50.00",
            "purchases14d": "2",
        }
    ])[0]
    product = sync._transform_product_data([
        {
            "campaignId": "1",
            "adGroupId": "2",
            "advertisedAsin": "B000TEST",
            "advertisedSku": "SKU-1",
            "unitsSoldClicks14d": "3",
        }
    ])[0]

    assert campaign["campaign_budget"] == 25.0
    assert product["asin"] == "B000TEST"
    assert product["sku"] == "SKU-1"
    assert product["units_sold"] == 3
