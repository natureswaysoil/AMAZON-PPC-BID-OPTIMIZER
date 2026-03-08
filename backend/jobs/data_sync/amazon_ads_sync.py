# backend/jobs/data_sync/amazon_ads_sync.py
"""
Amazon Ads Data Sync Job - API v3
Syncs campaign, keyword, and product performance data from Amazon Ads to BigQuery
"""
import logging
import json
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any
from google.cloud import bigquery
from shared.amazon_client import amazon_client
from core.config import settings

logger = logging.getLogger(__name__)


class AmazonAdsSync:
    """Sync Amazon Ads data using API v3 reporting format"""
    
    def __init__(self):
        self.amazon_client = amazon_client
        self.bq_client = bigquery.Client(project=settings.PROJECT_ID)
        self.dataset = settings.BIGQUERY_DATASET
        
    def run(self):
        """Main sync process"""
        logger.info("=" * 60)
        logger.info("🔄 Starting Amazon Ads Data Sync (API v3)")
        logger.info(f"Project: {settings.PROJECT_ID}")
        logger.info(f"Dataset: {self.dataset}")
        logger.info(f"Region: {self.amazon_client.region}")
        logger.info(f"Endpoint: {self.amazon_client.base_url}")
        logger.info("=" * 60)
        logger.info("")
        
        # Sync keywords performance (last 30 days)
        try:
            logger.info("📊 Step 1: Syncing keywords performance...")
            keywords_data = self.sync_keywords_performance()
            logger.info(f"✅ Synced {len(keywords_data)} keyword records")
        except Exception as e:
            logger.error(f"❌ Keywords sync failed: {e}")
            logger.error("Continuing with other syncs...")
        
        logger.info("")
        
        # Sync campaign performance (last 14 days, daily)
        try:
            logger.info("📊 Step 2: Syncing campaign performance...")
            campaign_data = self.sync_campaign_performance()
            logger.info(f"✅ Synced {len(campaign_data)} campaign records")
        except Exception as e:
            logger.error(f"❌ Campaign sync failed: {e}")
            logger.error("Continuing with other syncs...")
        
        logger.info("")
        
        # Sync advertised product metrics (last 30 days)
        try:
            logger.info("📊 Step 3: Syncing advertised product metrics...")
            product_data = self.sync_advertised_product_metrics()
            logger.info(f"✅ Synced {len(product_data)} product records")
        except Exception as e:
            logger.error(f"❌ Product metrics sync failed: {e}")
            logger.error("Continuing...")
        
        logger.info("")

        # Sync search terms for keyword harvesting
        try:
            logger.info("📊 Step 4: Syncing search term reports...")
            search_data = self.sync_search_terms()
            logger.info(f"✅ Synced {len(search_data)} search term records")
        except Exception as e:
            logger.error(f"❌ Search term sync failed: {e}")
            logger.error("Continuing...")

        logger.info("")
        logger.info("=" * 60)
        logger.info("✅ Amazon Ads Data Sync Complete")
        logger.info("=" * 60)
    
    def sync_keywords_performance(self) -> List[Dict]:
        """Sync keyword performance data (30-day summary)"""
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=30)
        
        # Build report configuration using v3 format
        report_config = {
            "name": "Keywords Performance Report",
            "startDate": start_date.strftime('%Y-%m-%d'),
            "endDate": end_date.strftime('%Y-%m-%d'),
            "configuration": {
                "adProduct": "SPONSORED_PRODUCTS",
                "groupBy": ["keyword"],
                "columns": [
                    "campaignId",
                    "campaignName",
                    "adGroupId",
                    "adGroupName",
                    "keywordId",
                    "keywordText",
                    "keywordBid",
                    "matchType",
                    "impressions",
                    "clicks",
                    "cost",
                    "purchases",
                    "sales",
                    "purchases1d",
                    "purchases7d",
                    "purchases14d",
                    "purchases30d"
                ],
                "reportTypeId": "spTargetingKeyword",
                "timeUnit": "SUMMARY",  # Aggregate across date range
                "format": "GZIP_JSON"
            }
        }
        
        logger.info(f"Requesting keywords report: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        
        try:
            # Request and download report
            report_data = self.amazon_client.request_and_download_report_v3(
                report_config,
                max_wait=300
            )
            
            if not report_data:
                logger.warning("⚠️ No keyword data returned")
                return []
            
            # Transform and load to BigQuery
            transformed = self._transform_keywords_data(report_data)
            self._load_to_bigquery('sp_keywords', transformed)
            
            return transformed
            
        except Exception as e:
            logger.error(f"❌ Keywords report failed: {e}")
            logger.error(f"Report config: {json.dumps(report_config, indent=2)}")
            logger.error("This usually means:")
            logger.error("  1. Invalid date range")
            logger.error("  2. Missing columns in reportTypeId")
            logger.error("  3. Wrong adProduct for your account")
            raise
    
    def sync_campaign_performance(self) -> List[Dict]:
        """Sync daily campaign performance (last 14 days)"""
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=14)
        
        report_config = {
            "name": "Campaign Performance Report",
            "startDate": start_date.strftime('%Y-%m-%d'),
            "endDate": end_date.strftime('%Y-%m-%d'),
            "configuration": {
                "adProduct": "SPONSORED_PRODUCTS",
                "groupBy": ["campaign"],
                "columns": [
                    "date",
                    "campaignId",
                    "campaignName",
                    "campaignStatus",
                    "campaignBudget",
                    "impressions",
                    "clicks",
                    "cost",
                    "purchases",
                    "sales"
                ],
                "reportTypeId": "spCampaigns",
                "timeUnit": "DAILY",  # Daily breakdown
                "format": "GZIP_JSON"
            }
        }
        
        logger.info(f"Requesting campaign report: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        
        try:
            report_data = self.amazon_client.request_and_download_report_v3(
                report_config,
                max_wait=300
            )
            
            if not report_data:
                logger.warning("⚠️ No campaign data returned")
                return []
            
            # Transform and load to BigQuery
            transformed = self._transform_campaign_data(report_data)
            self._load_to_bigquery('sp_campaign_performance', transformed)
            
            return transformed
            
        except Exception as e:
            logger.error(f"❌ Campaign report failed: {e}")
            logger.error(f"Report config: {json.dumps(report_config, indent=2)}")
            raise
    
    def sync_advertised_product_metrics(self) -> List[Dict]:
        """Sync advertised product metrics for AOV calculation"""
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=30)
        
        report_config = {
            "name": "Advertised Product Report",
            "startDate": start_date.strftime('%Y-%m-%d'),
            "endDate": end_date.strftime('%Y-%m-%d'),
            "configuration": {
                "adProduct": "SPONSORED_PRODUCTS",
                "groupBy": ["advertiser"],
                "columns": [
                    "campaignId",
                    "adGroupId",
                    "asin",
                    "sku",
                    "impressions",
                    "clicks",
                    "cost",
                    "purchases",
                    "sales",
                    "purchases1d",
                    "purchases7d",
                    "purchases14d",
                    "purchases30d",
                    "unitsSold14d"
                ],
                "reportTypeId": "spAdvertisedProduct",
                "timeUnit": "SUMMARY",
                "format": "GZIP_JSON"
            }
        }
        
        logger.info(f"Requesting product report: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        
        try:
            report_data = self.amazon_client.request_and_download_report_v3(
                report_config,
                max_wait=300
            )
            
            if not report_data:
                logger.warning("⚠️ No product data returned")
                return []
            
            # Transform and load to BigQuery
            transformed = self._transform_product_data(report_data)
            self._load_to_bigquery('sp_advertised_product_metrics', transformed)
            
            return transformed
            
        except Exception as e:
            logger.error(f"❌ Product report failed: {e}")
            logger.error(f"Report config: {json.dumps(report_config, indent=2)}")
            raise
    
    def _transform_keywords_data(self, raw_data: List[Dict]) -> List[Dict]:
        """Transform keyword report data to BigQuery schema"""
        transformed = []
        sync_date = datetime.now(timezone.utc).date()
        now_utc = datetime.now(timezone.utc)
        
        for row in raw_data:
            # Calculate derived metrics
            clicks = int(row.get('clicks', 0))
            impressions = int(row.get('impressions', 0))
            cost = float(row.get('cost', 0))
            sales = float(row.get('sales', 0))
            purchases = int(row.get('purchases', 0))
            
            ctr = (clicks / impressions) if impressions > 0 else 0
            cvr = (purchases / clicks) if clicks > 0 else 0
            acos = (cost / sales) if sales > 0 else 0
            
            transformed.append({
                'keyword_id': int(row.get('keywordId', 0)),
                'keyword_text': row.get('keywordText', ''),
                'keyword_bid': float(row.get('keywordBid', 0)),
                'match_type': row.get('matchType', ''),
                'campaign_id': int(row.get('campaignId', 0)),
                'campaign_name': row.get('campaignName', ''),
                'ad_group_id': int(row.get('adGroupId', 0)),
                'ad_group_name': row.get('adGroupName', ''),
                'impressions': impressions,
                'clicks': clicks,
                'cost': cost,
                'purchases': purchases,
                'sales': sales,
                'purchases_1d': int(row.get('purchases1d', 0)),
                'purchases_7d': int(row.get('purchases7d', 0)),
                'purchases_14d': int(row.get('purchases14d', 0)),
                'purchases_30d': int(row.get('purchases30d', 0)),
                'ctr': ctr,
                'cvr': cvr,
                'acos': acos,
                'sync_date': sync_date.isoformat(),
                'updated_at': now_utc.isoformat()
            })
        
        return transformed
    
    def _transform_campaign_data(self, raw_data: List[Dict]) -> List[Dict]:
        """Transform campaign report data to BigQuery schema"""
        transformed = []
        now_utc = datetime.now(timezone.utc)
        
        for row in raw_data:
            # Calculate derived metrics
            cost = float(row.get('cost', 0))
            sales = float(row.get('sales', 0))
            
            acos = (cost / sales) if sales > 0 else 0
            roas = (sales / cost) if cost > 0 else 0
            
            transformed.append({
                'campaign_id': int(row.get('campaignId', 0)),
                'campaign_name': row.get('campaignName', ''),
                'campaign_status': row.get('campaignStatus', ''),
                'campaign_budget': float(row.get('campaignBudget', 0)),
                'date': row.get('date', datetime.now(timezone.utc).date().isoformat()),
                'impressions': int(row.get('impressions', 0)),
                'clicks': int(row.get('clicks', 0)),
                'cost': cost,
                'purchases': int(row.get('purchases', 0)),
                'sales': sales,
                'acos': acos,
                'roas': roas,
                'updated_at': now_utc.isoformat()
            })
        
        return transformed
    
    def _transform_product_data(self, raw_data: List[Dict]) -> List[Dict]:
        """Transform product report data to BigQuery schema"""
        transformed = []
        sync_date = datetime.now(timezone.utc).date()
        now_utc = datetime.now(timezone.utc)
        
        for row in raw_data:
            purchases = int(row.get('purchases', 0))
            sales = float(row.get('sales', 0))
            units_sold = int(row.get('unitsSold14d', 0))
            
            # Calculate AOV (will be overridden by GENERATED column in BigQuery)
            aov = (sales / purchases) if purchases > 0 else 0
            
            transformed.append({
                'campaign_id': int(row.get('campaignId')) if row.get('campaignId') is not None else None,
                'ad_group_id': int(row.get('adGroupId')) if row.get('adGroupId') is not None else None,
                'asin': row.get('asin', ''),
                'sku': row.get('sku', ''),
                'impressions': int(row.get('impressions', 0)),
                'clicks': int(row.get('clicks', 0)),
                'cost': float(row.get('cost', 0)),
                'purchases': purchases,
                'sales': sales,
                'units_sold': units_sold,
                'sync_date': sync_date.isoformat(),
                'updated_at': now_utc.isoformat()
            })
        
        return transformed
    
    def _load_to_bigquery(self, table_name: str, data: List[Dict]):
        """Load data to BigQuery table"""
        if not data:
            logger.warning(f"No data to load to {table_name}")
            return
        
        table_id = f"{settings.PROJECT_ID}.{self.dataset}.{table_name}"
        
        logger.info(f"Loading {len(data)} rows to {table_id}...")
        
        # Use WRITE_APPEND for incremental data to preserve history
        # Note: For production, implement deduplication logic based on date/id
        job_config = bigquery.LoadJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        )
        
        try:
            job = self.bq_client.load_table_from_json(
                data,
                table_id,
                job_config=job_config
            )
            job.result()  # Wait for completion
            
            logger.info(f"✅ Loaded {len(data)} rows to {table_name}")
            
        except Exception as e:
            logger.error(f"❌ Failed to load data to {table_name}: {e}")
            raise


    def sync_search_terms(self) -> list:
        """Sync search term report to BigQuery for keyword harvesting"""
        from datetime import datetime, timezone, timedelta
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
                    "impressions", "clicks", "cost",
                    "purchases14d", "sales14d", "acosClicks14d"
                ],
                "reportTypeId": "spSearchTerm",
                "timeUnit": "SUMMARY",
                "format": "GZIP_JSON"
            }
        }
        logger.info("Requesting search term report from Amazon...")
        try:
            data = self.amazon_client.request_and_download_report_v3(report_config, max_wait=300)
            if not data:
                logger.warning("⚠️ No search term data returned")
                return []
            today = end_date.strftime("%Y-%m-%d")
            for row in data:
                row["date"] = today
            self._load_to_bigquery("search_term_reports", data)
            logger.info(f"✅ Synced {len(data)} search terms")
            return data
        except Exception as e:
            logger.error(f"❌ Search term sync failed: {e}")
            return []

def run_amazon_ads_sync():
    """Entry point for the Amazon Ads sync job"""
    sync = AmazonAdsSync()
    sync.run()
