# backend/jobs/data_sync/amazon_ads_sync.py
"""Amazon Ads API v3 reporting sync."""
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from typing import Dict, List

from google.cloud import bigquery

from core.bigquery_upsert import BigQueryUpsertLoader
from core.config import settings
from shared.amazon_client import amazon_client
from shared.reporting_v3 import request_and_download_report_v3

logger = logging.getLogger(__name__)


def _safe_int(value, default=0):
    if value in (None, ""):
        return default
    return int(value)


def _safe_float(value, default=0.0):
    if value in (None, ""):
        return default
    return float(value)


class AmazonAdsSync:
    """Sync Amazon Ads reports into BigQuery with idempotent upserts."""

    def __init__(self):
        self.amazon_client = amazon_client
        self.bq_client = bigquery.Client(project=settings.PROJECT_ID)
        self.dataset = settings.BIGQUERY_DATASET
        self.upsert_loader = BigQueryUpsertLoader(
            self.bq_client,
            settings.PROJECT_ID,
            self.dataset,
        )

    @staticmethod
    def _error_details(exc: Exception) -> str:
        """Return Amazon's response body when a request raises an HTTP error."""
        response = getattr(exc, "response", None)
        if response is None:
            return str(exc)
        body = (getattr(response, "text", "") or "").strip()
        status = getattr(response, "status_code", "unknown")
        return f"HTTP {status}: {body or str(exc)}"

    def _request_report(self, report_config: Dict) -> List[Dict]:
        return request_and_download_report_v3(
            self.amazon_client,
            report_config,
            max_wait=1800,
        )

    def run(self):
        """Run all reports concurrently and fail if every report fails."""
        logger.info("=" * 60)
        logger.info("Starting Amazon Ads Data Sync (API v3)")
        logger.info("Project: %s", settings.PROJECT_ID)
        logger.info("Dataset: %s", self.dataset)
        logger.info("Region: %s", self.amazon_client.region)
        logger.info("Endpoint: %s", self.amazon_client.base_url)
        logger.info("=" * 60)

        jobs = (
            ("keywords", self.sync_keywords_performance),
            ("campaigns", self.sync_campaign_performance),
            ("advertised products", self.sync_advertised_product_metrics),
            ("search terms", self.sync_search_terms),
        )
        successes = 0
        failures = []

        logger.info("Submitting %s Amazon reports concurrently", len(jobs))
        with ThreadPoolExecutor(max_workers=len(jobs)) as executor:
            futures = {executor.submit(job): name for name, job in jobs}
            for future in as_completed(futures):
                name = futures[future]
                try:
                    rows = future.result()
                    successes += 1
                    logger.info("Synced %s %s records", len(rows), name)
                except Exception as exc:
                    details = self._error_details(exc)
                    failures.append((name, details))
                    logger.error("%s sync failed: %s", name.title(), details)
                    logger.error("Continuing with other syncs...")

        if failures:
            logger.warning(
                "Amazon Ads sync summary: %s succeeded, %s failed",
                successes,
                len(failures),
            )

        if successes == 0:
            summary = "; ".join(f"{name}: {details}" for name, details in failures)
            raise RuntimeError(f"All Amazon Ads report syncs failed. {summary}")

        logger.info("Amazon Ads Data Sync Complete")

    def sync_keywords_performance(self) -> List[Dict]:
        """Sync a rolling 30-day keyword-targeting summary."""
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=30)
        report_config = {
            "name": "Keywords Performance Report",
            "startDate": start_date.strftime("%Y-%m-%d"),
            "endDate": end_date.strftime("%Y-%m-%d"),
            "configuration": {
                "adProduct": "SPONSORED_PRODUCTS",
                "groupBy": ["targeting"],
                "columns": [
                    "campaignId", "campaignName", "adGroupId", "adGroupName",
                    "keywordId", "keyword", "keywordBid", "matchType",
                    "impressions", "clicks", "cost", "purchases14d", "sales14d",
                    "purchases1d", "purchases7d", "purchases30d",
                ],
                "reportTypeId": "spTargeting",
                "timeUnit": "SUMMARY",
                "format": "GZIP_JSON",
            },
        }
        logger.info(
            "Requesting keywords report: %s to %s",
            report_config["startDate"],
            report_config["endDate"],
        )
        try:
            report_data = self._request_report(report_config)
            if not report_data:
                logger.warning("No keyword data returned")
                return []
            transformed = self._transform_keywords_data(report_data)
            self._load_to_bigquery("sp_keyword_performance", transformed)
            return transformed
        except Exception:
            logger.error("Report config: %s", json.dumps(report_config, indent=2))
            raise

    def sync_campaign_performance(self) -> List[Dict]:
        """Sync daily campaign performance for the last 14 days."""
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=14)
        report_config = {
            "name": "Campaign Performance Report",
            "startDate": start_date.strftime("%Y-%m-%d"),
            "endDate": end_date.strftime("%Y-%m-%d"),
            "configuration": {
                "adProduct": "SPONSORED_PRODUCTS",
                "groupBy": ["campaign"],
                "columns": [
                    "date", "campaignId", "campaignName", "campaignStatus",
                    "campaignBudgetAmount", "impressions", "clicks", "cost",
                    "purchases14d", "sales14d",
                ],
                "reportTypeId": "spCampaigns",
                "timeUnit": "DAILY",
                "format": "GZIP_JSON",
            },
        }
        logger.info(
            "Requesting campaign report: %s to %s",
            report_config["startDate"],
            report_config["endDate"],
        )
        try:
            report_data = self._request_report(report_config)
            if not report_data:
                logger.warning("No campaign data returned")
                return []
            transformed = self._transform_campaign_data(report_data)
            self._load_to_bigquery("sp_campaign_performance", transformed)
            return transformed
        except Exception:
            logger.error("Report config: %s", json.dumps(report_config, indent=2))
            raise

    def sync_advertised_product_metrics(self) -> List[Dict]:
        """Sync a rolling 30-day advertised-product summary."""
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=30)
        report_config = {
            "name": "Advertised Product Report",
            "startDate": start_date.strftime("%Y-%m-%d"),
            "endDate": end_date.strftime("%Y-%m-%d"),
            "configuration": {
                "adProduct": "SPONSORED_PRODUCTS",
                "groupBy": ["advertiser"],
                "columns": [
                    "campaignId", "adGroupId", "advertisedAsin", "advertisedSku",
                    "impressions", "clicks", "cost", "purchases14d", "sales14d",
                    "purchases1d", "purchases7d", "purchases30d",
                    "unitsSoldClicks14d",
                ],
                "reportTypeId": "spAdvertisedProduct",
                "timeUnit": "SUMMARY",
                "format": "GZIP_JSON",
            },
        }
        logger.info(
            "Requesting product report: %s to %s",
            report_config["startDate"],
            report_config["endDate"],
        )
        try:
            report_data = self._request_report(report_config)
            if not report_data:
                logger.warning("No product data returned")
                return []
            transformed = self._transform_product_data(report_data)
            self._load_to_bigquery("sp_product_performance", transformed)
            return transformed
        except Exception:
            logger.error("Report config: %s", json.dumps(report_config, indent=2))
            raise

    def sync_search_terms(self) -> List[Dict]:
        """Sync a rolling 30-day search-term summary."""
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=30)
        report_config = {
            "name": "Search Term Report",
            "startDate": start_date.strftime("%Y-%m-%d"),
            "endDate": end_date.strftime("%Y-%m-%d"),
            "configuration": {
                "adProduct": "SPONSORED_PRODUCTS",
                "groupBy": ["searchTerm"],
                "columns": [
                    "campaignId", "campaignName", "adGroupId", "adGroupName",
                    "keywordId", "keywordBid", "matchType", "searchTerm",
                    "impressions", "clicks", "cost", "purchases14d",
                    "sales14d", "acosClicks14d",
                ],
                "reportTypeId": "spSearchTerm",
                "timeUnit": "SUMMARY",
                "format": "GZIP_JSON",
            },
        }
        logger.info("Requesting search term report from Amazon...")
        report_data = self._request_report(report_config)
        if not report_data:
            logger.warning("No search term data returned")
            return []
        transformed = self._transform_search_terms_data(report_data, end_date)
        self._load_to_bigquery("search_term_reports", transformed)
        return transformed

    def _transform_search_terms_data(
        self, raw_data: List[Dict], report_date
    ) -> List[Dict]:
        today = report_date.strftime("%Y-%m-%d")
        transformed = []
        for row in raw_data:
            transformed.append({
                "campaign_id": _safe_int(row.get("campaignId")),
                "campaign_name": str(row.get("campaignName") or ""),
                "ad_group_id": _safe_int(row.get("adGroupId")),
                "ad_group_name": str(row.get("adGroupName") or ""),
                "keyword_id": _safe_int(row.get("keywordId")),
                "keyword_bid": _safe_float(row.get("keywordBid")),
                "match_type": str(row.get("matchType") or ""),
                "search_term": str(row.get("searchTerm") or ""),
                "impressions": _safe_int(row.get("impressions")),
                "clicks": _safe_int(row.get("clicks")),
                "cost": _safe_float(row.get("cost")),
                "purchases_14d": _safe_int(row.get("purchases14d")),
                "sales_14d": _safe_float(row.get("sales14d")),
                "acos_clicks_14d": _safe_float(row.get("acosClicks14d")),
                "date": today,
            })
        return transformed

    def _transform_keywords_data(self, raw_data: List[Dict]) -> List[Dict]:
        transformed = []
        sync_date = datetime.now(timezone.utc).date().isoformat()
        now_utc = datetime.now(timezone.utc).isoformat()
        for row in raw_data:
            clicks = _safe_int(row.get("clicks"))
            impressions = _safe_int(row.get("impressions"))
            cost = _safe_float(row.get("cost"))
            sales = _safe_float(row.get("sales14d", row.get("sales")))
            purchases = _safe_int(row.get("purchases14d", row.get("purchases")))
            transformed.append({
                "keyword_id": _safe_int(row.get("keywordId")),
                "keyword_text": row.get("keyword", row.get("keywordText", "")),
                "keyword_bid": _safe_float(row.get("keywordBid")),
                "match_type": row.get("matchType", ""),
                "campaign_id": _safe_int(row.get("campaignId")),
                "campaign_name": row.get("campaignName", ""),
                "ad_group_id": _safe_int(row.get("adGroupId")),
                "ad_group_name": row.get("adGroupName", ""),
                "impressions": impressions,
                "clicks": clicks,
                "cost": cost,
                "purchases": purchases,
                "sales": sales,
                "purchases_1d": _safe_int(row.get("purchases1d")),
                "purchases_7d": _safe_int(row.get("purchases7d")),
                "purchases_14d": _safe_int(row.get("purchases14d")),
                "purchases_30d": _safe_int(row.get("purchases30d")),
                "ctr": clicks / impressions if impressions else 0,
                "cvr": purchases / clicks if clicks else 0,
                "acos": cost / sales if sales else 0,
                "sync_date": sync_date,
                "updated_at": now_utc,
            })
        return transformed

    def _transform_campaign_data(self, raw_data: List[Dict]) -> List[Dict]:
        transformed = []
        now_utc = datetime.now(timezone.utc).isoformat()
        for row in raw_data:
            cost = _safe_float(row.get("cost"))
            sales = _safe_float(row.get("sales14d", row.get("sales")))
            transformed.append({
                "campaign_id": _safe_int(row.get("campaignId")),
                "campaign_name": row.get("campaignName", ""),
                "campaign_status": row.get("campaignStatus", ""),
                "campaign_budget": _safe_float(
                    row.get("campaignBudgetAmount", row.get("campaignBudget", 0))
                ),
                "date": row.get("date", datetime.now(timezone.utc).date().isoformat()),
                "impressions": _safe_int(row.get("impressions")),
                "clicks": _safe_int(row.get("clicks")),
                "cost": cost,
                "purchases": _safe_int(row.get("purchases14d", row.get("purchases"))),
                "sales": sales,
                "acos": cost / sales if sales else 0,
                "roas": sales / cost if cost else 0,
                "updated_at": now_utc,
            })
        return transformed

    def _transform_product_data(self, raw_data: List[Dict]) -> List[Dict]:
        transformed = []
        sync_date = datetime.now(timezone.utc).date().isoformat()
        now_utc = datetime.now(timezone.utc).isoformat()
        for row in raw_data:
            transformed.append({
                "campaign_id": _safe_int(row.get("campaignId"), None),
                "ad_group_id": _safe_int(row.get("adGroupId"), None),
                "asin": row.get("advertisedAsin", row.get("asin", "")),
                "sku": row.get("advertisedSku", row.get("sku", "")),
                "impressions": _safe_int(row.get("impressions")),
                "clicks": _safe_int(row.get("clicks")),
                "cost": _safe_float(row.get("cost")),
                "purchases": _safe_int(row.get("purchases14d", row.get("purchases"))),
                "sales": _safe_float(row.get("sales14d", row.get("sales"))),
                "units_sold": _safe_int(
                    row.get("unitsSoldClicks14d", row.get("unitsSold14d", 0))
                ),
                "sync_date": sync_date,
                "updated_at": now_utc,
            })
        return transformed

    def _load_to_bigquery(self, table_name: str, data: List[Dict]):
        """Merge a report snapshot into BigQuery without creating duplicates."""
        if not data:
            logger.warning("No data to load to %s", table_name)
            return {"source_rows": 0, "affected_rows": 0}
        result = self.upsert_loader.load(table_name, data)
        logger.info(
            "Loaded %s rows into %s using deduplicating MERGE",
            result["source_rows"],
            table_name,
        )
        return result


def run_amazon_ads_sync():
    """Cloud Run entry point."""
    AmazonAdsSync().run()
