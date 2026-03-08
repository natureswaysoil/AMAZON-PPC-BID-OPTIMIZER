"""Sync Amazon Ads data - Updated for SD campaigns"""
from google.cloud import bigquery
import sys
sys.path.insert(0, '/app')

from backend.core.secrets import secret_manager
from backend.core.config import settings
from backend.core.amazon_api.ads_api import AmazonAdsAPI
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class AdsDataSync:
    def __init__(self):
        self.bq_client = bigquery.Client(project=settings.PROJECT_ID)
        
        ads_creds = secret_manager.get_amazon_ads_credentials()
        self.ads_api = AmazonAdsAPI(ads_creds)
    
    def sync_campaigns(self):
        """Sync all campaign types"""
        logger.info("Syncing campaigns...")
        
        try:
            campaigns = self.ads_api.get_campaigns()
            
            if not campaigns:
                logger.warning("No campaigns found")
                return
            
            logger.info(f"Found {len(campaigns)} campaigns")
            
            rows = []
            for camp in campaigns:
                rows.append({
                    'campaign_id': camp.get('campaignId'),
                    'campaign_name': camp.get('name'),
                    'state': camp.get('state'),
                    'daily_budget': camp.get('budget') or camp.get('dailyBudget'),
                    'start_date': camp.get('startDate'),
                    'targeting_type': camp.get('tactic') or camp.get('targetingType'),
                    'updated_at': datetime.utcnow().isoformat()
                })
            
            table_id = f"{settings.PROJECT_ID}.{settings.BIGQUERY_DATASET}.campaigns"
            
            # Clear and reload
            delete_query = f"DELETE FROM `{table_id}` WHERE campaign_id >= 1000"
            self.bq_client.query(delete_query).result()
            
            job_config = bigquery.LoadJobConfig(
                write_disposition="WRITE_APPEND",
                schema_update_options=[bigquery.SchemaUpdateOption.ALLOW_FIELD_ADDITION]
            )
            
            job = self.bq_client.load_table_from_json(rows, table_id, job_config=job_config)
            job.result()
            
            logger.info(f"✅ Synced {len(rows)} campaigns")
            
        except Exception as e:
            logger.error(f"Failed to sync campaigns: {e}", exc_info=True)
    
    def sync_keywords(self):
        """Sync keywords and targets"""
        logger.info("Syncing keywords/targets...")
        
        try:
            keywords = self.ads_api.get_keywords()
            
            if not keywords:
                logger.warning("No keywords found")
                return
            
            logger.info(f"Found {len(keywords)} keywords/targets")
            
            rows = []
            for kw in keywords:
                rows.append({
                    'keyword_id': kw.get('targetId') or kw.get('keywordId'),
                    'campaign_id': kw.get('campaignId'),
                    'ad_group_id': kw.get('adGroupId'),
                    'keyword_text': kw.get('expression') or kw.get('keywordText') or 'SD_TARGET',
                    'match_type': kw.get('expressionType') or kw.get('matchType') or 'AUTO',
                    'bid': kw.get('bid'),
                    'state': kw.get('state'),
                    'updated_at': datetime.utcnow().isoformat()
                })
            
            if rows:
                table_id = f"{settings.PROJECT_ID}.{settings.BIGQUERY_DATASET}.keywords"
                
                delete_query = f"DELETE FROM `{table_id}` WHERE keyword_id >= 10000"
                self.bq_client.query(delete_query).result()
                
                job_config = bigquery.LoadJobConfig(
                    write_disposition="WRITE_APPEND",
                    schema_update_options=[bigquery.SchemaUpdateOption.ALLOW_FIELD_ADDITION]
                )
                
                job = self.bq_client.load_table_from_json(rows, table_id, job_config=job_config)
                job.result()
                
                logger.info(f"✅ Synced {len(rows)} keywords/targets")
        
        except Exception as e:
            logger.error(f"Failed to sync keywords: {e}", exc_info=True)

def run_ads_sync():
    """Entry point"""
    logger.info("Starting Amazon Ads data sync...")
    
    sync = AdsDataSync()
    sync.sync_campaigns()
    sync.sync_keywords()
    
    logger.info("✅ Ads data sync complete!")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_ads_sync()
