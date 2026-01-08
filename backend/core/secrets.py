# backend/core/secrets.py
from google.cloud import secretmanager
from functools import lru_cache
import json
import logging
from typing import Dict
from .config import settings

logger = logging.getLogger(__name__)

class SecretManager:
    """Google Cloud Secret Manager client"""
    
    def __init__(self, project_id: str = None):
        self.project_id = project_id or settings.PROJECT_ID
        self.client = secretmanager.SecretManagerServiceClient()
    
    @lru_cache(maxsize=128)
    def get_secret(self, secret_id: str, version: str = "latest") -> str:
        """Retrieve secret from Google Secret Manager"""
        try:
            name = f"projects/{self.project_id}/secrets/{secret_id}/versions/{version}"
            response = self.client.access_secret_version(request={"name": name})
            return response.payload.data.decode("UTF-8")
        except Exception as e:
            logger.error(f"Failed to get secret {secret_id}: {e}")
            raise
    
    def get_amazon_ads_credentials(self, account_name: str = "default") -> Dict:
        """Get Amazon Ads API credentials"""
        secret_data = self.get_secret(f"amazon-ads-{account_name}")
        return json.loads(secret_data)
    
    def get_amazon_sp_credentials(self, account_name: str = "default") -> Dict:
        """Get Amazon SP-API credentials"""
        secret_data = self.get_secret(f"amazon-sp-{account_name}")
        return json.loads(secret_data)

# Global instance
secret_manager = SecretManager()
