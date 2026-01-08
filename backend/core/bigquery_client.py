# backend/core/bigquery_client.py
from google.cloud import bigquery
from .config import settings
import logging

logger = logging.getLogger(__name__)

class BigQueryClient:
    """BigQuery client wrapper"""
    
    def __init__(self):
        self.client = bigquery.Client(project=settings.PROJECT_ID)
        self.dataset = settings.BIGQUERY_DATASET
    
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
