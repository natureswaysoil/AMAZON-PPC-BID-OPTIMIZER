# backend/aov_fetcher.py
# Note: Uses absolute imports relative to backend directory (Docker container root)
from google.cloud import bigquery
from dataclasses import dataclass
from typing import Dict
import logging
from core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class AOVData:
    aov: float
    confidence: str
    orders: int = 0


class AOVFetcher:
    """Fetches campaign-level AOV data from synced Amazon Ads metrics."""

    def __init__(self):
        self._bq_client = None
        self._aov_cache: Dict[str, AOVData] = {}

    @property
    def bq_client(self):
        """Lazy initialization of BigQuery client."""
        if self._bq_client is None:
            self._bq_client = bigquery.Client(project=settings.PROJECT_ID)
        return self._bq_client

    def fetch_all(self):
        """Fetch campaign AOV from the rolling advertised-product snapshot."""
        self._aov_cache.clear()
        query = f"""
        SELECT
            campaign_id,
            SAFE_DIVIDE(SUM(sales), NULLIF(SUM(purchases), 0)) AS aov,
            CAST(SUM(purchases) AS INT64) AS orders
        FROM `{settings.PROJECT_ID}.{settings.BIGQUERY_DATASET}.sp_advertised_product_metrics`
        WHERE sync_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
          AND campaign_id IS NOT NULL
        GROUP BY campaign_id
        HAVING SUM(purchases) > 0
        """

        try:
            results = self.bq_client.query(query).result()
        except Exception as exc:
            raise RuntimeError(
                "Required AOV source table sp_advertised_product_metrics is unavailable "
                "or unreadable. Run a successful ads-data-sync before the optimizer."
            ) from exc

        for row in results:
            campaign_id = str(row["campaign_id"])
            aov = float(row["aov"]) if row["aov"] else 30.0
            orders = int(row["orders"]) if row["orders"] else 0

            if orders >= 10:
                confidence = "high"
            elif orders >= 5:
                confidence = "medium"
            else:
                confidence = "low"

            self._aov_cache[campaign_id] = AOVData(
                aov=aov,
                confidence=confidence,
                orders=orders,
            )

        logger.info("Fetched AOV data for %s campaigns", len(self._aov_cache))

    def get_aov(self, campaign_id: str) -> AOVData:
        """Get AOV for a specific campaign, using a conservative fallback."""
        campaign_id = str(campaign_id)

        if campaign_id in self._aov_cache:
            return self._aov_cache[campaign_id]

        logger.warning("No AOV data for campaign %s, using default", campaign_id)
        return AOVData(aov=30.0, confidence="low", orders=0)


# Global singleton instance
aov_fetcher = AOVFetcher()
