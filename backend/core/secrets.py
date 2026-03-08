from google.cloud import secretmanager
import json
import os
from functools import lru_cache

class SecretManager:
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.client = secretmanager.SecretManagerServiceClient()
    
    @lru_cache(maxsize=128)
    def get_secret(self, secret_id: str, version: str = "latest") -> str:
        name = f"projects/{self.project_id}/secrets/{secret_id}/versions/{version}"
        response = self.client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")
    
    def get_amazon_ads_credentials(self) -> dict:
        """Get Amazon Ads credentials from separate secrets"""
        return {
            'client_id': self.get_secret("AMAZON_CLIENT_ID"),
            'client_secret': self.get_secret("AMAZON_CLIENT_SECRET"),
            'refresh_token': self.get_secret("AMAZON_REFRESH_TOKEN"),
            'profile_id': self.get_secret("AMAZON_PROFILE_ID"),
            'region': 'NA'
        }
    
    def get_amazon_sp_credentials(self) -> dict:
        try:
            # If you have SP-API credentials
            return {
                'refresh_token': self.get_secret("amazon-sp-refresh-token"),
                'lwa_app_id': self.get_secret("amazon-sp-app-id"),
                'lwa_client_secret': self.get_secret("amazon-sp-client-secret"),
            }
        except:
            return {}

secret_manager = SecretManager(os.getenv('GOOGLE_CLOUD_PROJECT', 'amazon-ppc-bid-optimizer'))
