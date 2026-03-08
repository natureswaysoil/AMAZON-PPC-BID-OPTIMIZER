"""
Campaign-level AOV fetcher (works with current schema)
"""

import os
import logging
from typing import Dict
from dataclasses import dataclass
from google.cloud import bigquery

logger = logging.getLogger(__name__)

PROJECT_ID = os.getenv("GCP_PROJECT", "amazon-ppc-474902")
DATASET = os.getenv("BQ_DATASET", "amazon_ppc")
DEFAULT_AOV = float(os.getenv("DEFAULT_AOV", "35.0"))

@dataclass
class CampaignAOV:
    campaign_id: str
    aov: float
    conversions: int
    confidence: str
    source: str

class AOVFetcher:
    """Fetches campaign-level AOV from BigQuery"""
    
    def __init__(self):
        self.client = bigquery.Client(project=PROJECT_ID)
        self._aov_14d: Dict[str, CampaignAOV] = {}
        self._aov_30d: Dict[str, CampaignAOV] = {}
        
    def fetch_all(self) -> None:
        """Fetch both 14d and 30d AOV maps"""
        logger.info("Fetching campaign AOV data from BigQuery...")
        self._aov_14d = self._fetch_aov_window(days=14, min_conversions=2)
        self._aov_30d = self._fetch_aov_window(days=30, min_conversions=2)
        logger.info(f"✓ Loaded AOV for {len(self._aov_14d)} campaigns (14d), "
                   f"{len(self._aov_30d)} campaigns (30d)")
    
    def _fetch_aov_window(self, days: int, min_conversions: int) -> Dict[str, CampaignAOV]:
        """Fetch AOV for a specific time window"""
        query = f"""
        SELECT
          campaign_id,
          SAFE_DIVIDE(SUM(conversion_value), NULLIF(SUM(conversions), 0)) AS aov,
          SUM(conversions) AS conversions,
          SUM(conversion_value) AS total_sales,
          COUNT(DISTINCT date) AS active_days
        FROM `{PROJECT_ID}.{DATASET}.keyword_performance`
        WHERE 
          date >= DATE_SUB(CURRENT_DATE(), INTERVAL @days DAY)
          AND conversion_value > 0
        GROUP BY campaign_id
        HAVING 
          conversions >= @min_conversions
          AND aov > 10
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("days", "INT64", days),
                bigquery.ScalarQueryParameter("min_conversions", "INT64", min_conversions),
            ]
        )
        
        try:
            rows = self.client.query(query, job_config=job_config).result()
            result = {}
            
            for row in rows:
                campaign_id = row["campaign_id"]
                aov = float(row["aov"])
                conversions = int(row["conversions"])
                active_days = int(row["active_days"])
                
                if conversions >= 10 and active_days >= 7:
                    confidence = "high"
                elif conversions >= 5:
                    confidence = "medium"
                else:
                    confidence = "low"
                
                result[campaign_id] = CampaignAOV(
                    campaign_id=campaign_id,
                    aov=aov,
                    conversions=conversions,
                    confidence=confidence,
                    source=f"{days}d"
                )
            
            return result
            
        except Exception as e:
            logger.error(f"BigQuery AOV fetch failed: {e}")
            return {}
    
    def get_aov(self, campaign_id: str) -> CampaignAOV:
        """Get AOV for campaign with intelligent fallback"""
        if campaign_id in self._aov_14d:
            return self._aov_14d[campaign_id]
        
        if campaign_id in self._aov_30d:
            return self._aov_30d[campaign_id]
        
        logger.debug(f"Using default AOV for campaign {campaign_id}")
        return CampaignAOV(
            campaign_id=campaign_id,
            aov=DEFAULT_AOV,
            conversions=0,
            confidence="default",
            source="default"
        )
    
    def get_aov_tier(self, campaign_id: str) -> str:
        """Classify campaign into AOV tier for bid ceiling lookup"""
        aov_data = self.get_aov(campaign_id)
        aov = aov_data.aov
        
        if aov < 30:
            return "L"
        elif aov < 46:
            return "M"
        elif aov < 70:
            return "H"
        else:
            return "X"

aov_fetcher = AOVFetcher()
