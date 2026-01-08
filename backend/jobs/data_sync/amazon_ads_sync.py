# jobs/data_sync/amazon_ads_sync.py
"""
Amazon Ads Data Sync Job

Syncs campaigns, keywords, and performance data from Amazon Ads API to BigQuery
"""
from google.cloud import bigquery
from datetime import datetime, timedelta
import logging
from typing import List, Dict
import sys
import os
from pathlib import Path

# Add parent directories to path
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))
sys.path.insert(0, '/app')

try:
    from backend.shared.amazon_client import amazon_client
    from backend.core.config import settings
except ImportError:
    from shared.amazon_client import amazon_client
    from core.config import settings

logger = logging.getLogger(__name__)

class AmazonAdsDataSync:
    """Sync Amazon Ads data to BigQuery"""
    
    def __init__(self):
        self.amazon_client = amazon_client
        self.bq_client = bigquery.Client(project=settings.PROJECT_ID)
        self.dataset = settings.BIGQUERY_DATASET
    
    def sync_campaigns(self):
        """Sync campaign metadata from Amazon"""
        logger.info("📊 Syncing campaigns from Amazon Ads API...")
        
        try:
            # Get campaigns via direct API call (not reports)
            campaigns = self.amazon_client.get_campaigns(state_filter=None)  # Get all states
            
            if not campaigns:
                logger.warning("⚠️ No campaigns found")
                return
            
            # Transform to BigQuery format
            rows = []
            for camp in campaigns:
                rows.append({
                    'campaign_id': int(camp['campaignId']),
                    'campaign_name': camp.get('name', ''),
                    'campaign_status': camp.get('state', 'UNKNOWN'),
                    'campaign_type': camp.get('targetingType', 'MANUAL'),
                    'daily_budget': float(camp.get('dailyBudget', 0)),
                    'start_date': camp.get('startDate'),
                    'end_date': camp.get('endDate'),
                    'updated_at': datetime.utcnow().isoformat()
                })
            
            # Load to BigQuery
            table_id = f"{settings.PROJECT_ID}.{self.dataset}.sp_campaigns"
            
            job_config = bigquery.LoadJobConfig(
                write_disposition="WRITE_TRUNCATE",  # Replace all data
                schema_update_options=[bigquery.SchemaUpdateOption.ALLOW_FIELD_ADDITION]
            )
            
            job = self.bq_client.load_table_from_json(rows, table_id, job_config=job_config)
            job.result()
            
            logger.info(f"✅ Synced {len(rows)} campaigns to BigQuery")
            
        except Exception as e:
            logger.error(f"❌ Failed to sync campaigns: {e}", exc_info=True)
    
    def sync_keywords(self):
        """Sync keyword metadata from Amazon"""
        logger.info("🔑 Syncing keywords from Amazon Ads API...")
        
        try:
            # Get keywords via direct API call
            keywords = self.amazon_client.get_keywords(state_filter=None)  # Get all states
            
            if not keywords:
                logger.warning("⚠️ No keywords found")
                return
            
            # Transform to BigQuery format
            rows = []
            for kw in keywords:
                rows.append({
                    'keyword_id': int(kw['keywordId']),
                    'campaign_id': int(kw['campaignId']),
                    'ad_group_id': int(kw['adGroupId']),
                    'keyword_text': kw.get('keywordText', ''),
                    'match_type': kw.get('matchType', 'EXACT'),
                    'bid': float(kw.get('bid', 0)),
                    'state': kw.get('state', 'ENABLED'),
                    'updated_at': datetime.utcnow().isoformat()
                })
            
            # Load to BigQuery
            table_id = f"{settings.PROJECT_ID}.{self.dataset}.sp_keywords"
            
            job_config = bigquery.LoadJobConfig(
                write_disposition="WRITE_TRUNCATE",
                schema_update_options=[bigquery.SchemaUpdateOption.ALLOW_FIELD_ADDITION]
            )
            
            job = self.bq_client.load_table_from_json(rows, table_id, job_config=job_config)
            job.result()
            
            logger.info(f"✅ Synced {len(rows)} keywords to BigQuery")
            
        except Exception as e:
            logger.error(f"❌ Failed to sync keywords: {e}", exc_info=True)
    
    def sync_campaign_performance(self, days_back: int = 14):
        """Sync campaign performance from Amazon Ads Reports API v3"""
        logger.info(f"📈 Syncing campaign performance (last {days_back} days)...")
        
        try:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days_back)
            
            # Use reports API v3
            report_data = self.amazon_client.get_campaigns_report(
                start_date=start_date.strftime('%Y-%m-%d'),
                end_date=end_date.strftime('%Y-%m-%d')
            )
            
            if not report_data:
                logger.warning("⚠️ No campaign performance data")
                return
            
            # Transform to BigQuery format
            rows = []
            for row in report_data:
                # Date is required for time-series data
                date_value = row.get('date')
                if not date_value:
                    logger.warning(f"⚠️ Skipping row with missing date: {row}")
                    continue
                
                rows.append({
                    'date': date_value,
                    'campaign_id': int(row.get('campaignId', 0)),
                    'impressions': int(row.get('impressions', 0)),
                    'clicks': int(row.get('clicks', 0)),
                    'cost': float(row.get('cost', 0)),
                    'sales': float(row.get('sales', 0)),
                    'purchases': int(row.get('purchases', 0)),
                    'updated_at': datetime.utcnow().isoformat()
                })
            
            # Load to BigQuery
            table_id = f"{settings.PROJECT_ID}.{self.dataset}.sp_campaign_performance"
            
            job_config = bigquery.LoadJobConfig(
                write_disposition="WRITE_APPEND",
                schema_update_options=[bigquery.SchemaUpdateOption.ALLOW_FIELD_ADDITION]
            )
            
            job = self.bq_client.load_table_from_json(rows, table_id, job_config=job_config)
            job.result()
            
            logger.info(f"✅ Synced {len(rows)} campaign performance rows")
            
        except Exception as e:
            logger.error(f"❌ Failed to sync campaign performance: {e}", exc_info=True)
    
    def sync_keyword_performance(self, days_back: int = 14):
        """Sync keyword performance from Amazon Ads Reports API v3"""
        logger.info(f"🎯 Syncing keyword performance (last {days_back} days)...")
        
        try:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days_back)
            
            # Use reports API v3
            report_data = self.amazon_client.get_keywords_report(
                start_date=start_date.strftime('%Y-%m-%d'),
                end_date=end_date.strftime('%Y-%m-%d')
            )
            
            if not report_data:
                logger.warning("⚠️ No keyword performance data")
                return
            
            # Transform to BigQuery format
            rows = []
            for row in report_data:
                # Date is required for time-series data
                date_value = row.get('date')
                if not date_value:
                    logger.warning(f"⚠️ Skipping row with missing date: {row}")
                    continue
                
                rows.append({
                    'date': date_value,
                    'keyword_id': int(row.get('keywordId', 0)),
                    'campaign_id': int(row.get('campaignId', 0)),
                    'ad_group_id': int(row.get('adGroupId', 0)),
                    'impressions': int(row.get('impressions', 0)),
                    'clicks': int(row.get('clicks', 0)),
                    'cost': float(row.get('cost', 0)),
                    'conversion_value': float(row.get('sales', 0)),
                    'conversions': int(row.get('purchases', 0)),
                    'updated_at': datetime.utcnow().isoformat()
                })
            
            # Load to BigQuery
            table_id = f"{settings.PROJECT_ID}.{self.dataset}.keyword_performance"
            
            job_config = bigquery.LoadJobConfig(
                write_disposition="WRITE_APPEND",
                schema_update_options=[bigquery.SchemaUpdateOption.ALLOW_FIELD_ADDITION]
            )
            
            job = self.bq_client.load_table_from_json(rows, table_id, job_config=job_config)
            job.result()
            
            logger.info(f"✅ Synced {len(rows)} keyword performance rows")
            
        except Exception as e:
            logger.error(f"❌ Failed to sync keyword performance: {e}", exc_info=True)
    
    def sync_advertised_products(self, days_back: int = 30):
        """
        Sync advertised product metrics to calculate AOV
        
        This uses campaign performance data joined with order data to calculate
        Average Order Value per campaign/ASIN
        """
        logger.info(f"📦 Calculating advertised product metrics (last {days_back} days)...")
        
        try:
            # Query to calculate AOV from orders and campaign data
            query = f"""
            CREATE OR REPLACE TABLE `{settings.PROJECT_ID}.{self.dataset}.sp_advertised_product_metrics` AS
            SELECT
                cp.campaign_id,
                DATE(cp.date) as date,
                COALESCE(SUM(cp.sales) / NULLIF(SUM(cp.purchases), 0), 30.0) as aov,
                SUM(cp.purchases) as orders,
                SUM(cp.sales) as revenue,
                CURRENT_TIMESTAMP() as updated_at
            FROM `{settings.PROJECT_ID}.{self.dataset}.sp_campaign_performance` cp
            WHERE cp.date >= DATE_SUB(CURRENT_DATE(), INTERVAL {days_back} DAY)
            GROUP BY cp.campaign_id, DATE(cp.date)
            """
            
            job = self.bq_client.query(query)
            job.result()
            
            logger.info("✅ Calculated advertised product metrics")
            
        except Exception as e:
            logger.error(f"❌ Failed to calculate product metrics: {e}", exc_info=True)
    
    def run_full_sync(self):
        """Run complete data sync"""
        logger.info("=" * 60)
        logger.info("🚀 Starting Amazon Ads Data Sync")
        logger.info("=" * 60)
        
        try:
            # 1. Sync metadata (campaigns, keywords)
            self.sync_campaigns()
            self.sync_keywords()
            
            # 2. Sync performance data (uses reports API)
            self.sync_campaign_performance(days_back=14)
            self.sync_keyword_performance(days_back=14)
            
            # 3. Calculate derived metrics
            self.sync_advertised_products(days_back=30)
            
            logger.info("=" * 60)
            logger.info("✅ Amazon Ads Data Sync Complete!")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"❌ Data sync failed: {e}", exc_info=True)
            raise


def run_data_sync():
    """Entry point for Cloud Run job"""
    try:
        syncer = AmazonAdsDataSync()
        syncer.run_full_sync()
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Sync job failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    run_data_sync()
