# backend/core/bigquery_client.py
from google.cloud import bigquery
from core.config import settings
import logging

logger = logging.getLogger(__name__)

class BigQueryClient:
    """BigQuery client wrapper"""
    
    def __init__(self):
        self._client = None
        self.dataset = settings.BIGQUERY_DATASET
    
    @property
    def client(self):
        """Lazy initialization of BigQuery client"""
        if self._client is None:
            self._client = bigquery.Client(project=settings.PROJECT_ID)
        return self._client
    
    def get_table_id(self, table_name: str) -> str:
        """Get fully qualified table ID"""
        return f"{settings.PROJECT_ID}.{self.dataset}.{table_name}"
    
    def query(self, query: str, **kwargs):
        """Execute a query"""
        return self.client.query(query, **kwargs)
    
    def load_table_from_json(self, rows, table_name: str, **kwargs):
        """Load data from JSON to table"""
        table_id = self.get_table_id(table_name)
        return self.client.load_table_from_json(rows, table_id, **kwargs)

# Global instance
bq_client = BigQueryClient()
