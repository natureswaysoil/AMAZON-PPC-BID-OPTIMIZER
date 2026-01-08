# backend/aov_fetcher.py
from google.cloud import bigquery
from dataclasses import dataclass
from typing import Dict, Optional
import logging
from .core.config import settings

logger = logging.getLogger(__name__)

@dataclass
class AOVData:
    aov: float
    confidence: str
    orders: int = 0
    
class AOVFetcher:
    """Fetches real-time AOV data from BigQuery or cache"""
    
    def __init__(self):
        self.bq_client = bigquery.Client(project=settings.PROJECT_ID)
        self._aov_cache: Dict[str, AOVData] = {}
    
    def fetch_all(self):
        """Fetch all AOV data from BigQuery and cache it"""
        query = f"""
        SELECT 
            campaign_id,
            AVG(aov_7d) as aov,
            COUNT(DISTINCT order_id) as orders
        FROM `{settings.PROJECT_ID}.{settings.BIGQUERY_DATASET}.asin_aov`
        WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
        GROUP BY campaign_id
        """
        
        try:
            results = self.bq_client.query(query).result()
            
            for row in results:
                campaign_id = str(row['campaign_id'])
                aov = float(row['aov']) if row['aov'] else 30.0
                orders = int(row['orders']) if row['orders'] else 0
                
                # Determine confidence based on order volume
                if orders >= 10:
                    confidence = 'high'
                elif orders >= 5:
                    confidence = 'medium'
                else:
                    confidence = 'low'
                
                self._aov_cache[campaign_id] = AOVData(
                    aov=aov,
                    confidence=confidence,
                    orders=orders
                )
            
            logger.info(f"Fetched AOV data for {len(self._aov_cache)} campaigns")
            
        except Exception as e:
            logger.error(f"Failed to fetch AOV data: {e}")
            # Continue with empty cache - will use defaults
    
    def get_aov(self, campaign_id: str) -> AOVData:
        """Get AOV for a specific campaign"""
        campaign_id = str(campaign_id)
        
        if campaign_id in self._aov_cache:
            return self._aov_cache[campaign_id]
        
        # Default fallback
        logger.warning(f"No AOV data for campaign {campaign_id}, using default")
        return AOVData(aov=30.0, confidence='low', orders=0)

# Global singleton instance
aov_fetcher = AOVFetcher()
