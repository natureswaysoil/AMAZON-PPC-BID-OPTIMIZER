# backend/shared/token_manager.py
"""
Amazon API OAuth Token Manager
Handles token refresh, caching, and validation
"""
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict
import logging
from threading import Lock
from core.config import settings
from core.secrets import secret_manager

logger = logging.getLogger(__name__)

class TokenManager:
    """
    Manages Amazon Advertising API OAuth tokens
    - Automatically refreshes expired tokens
    - Thread-safe token caching
    - Detailed logging for debugging
    """
    
    def __init__(self):
        self._access_token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None
        self._lock = Lock()
        self._credentials: Optional[Dict] = None
        
    def _load_credentials(self) -> Dict:
        """Load Amazon credentials from Secret Manager"""
        if self._credentials is None:
            try:
                # Load individual secrets as configured in settings
                client_id = secret_manager.get_secret(settings.AMAZON_CLIENT_ID_SECRET)
                client_secret = secret_manager.get_secret(settings.AMAZON_CLIENT_SECRET_SECRET)
                refresh_token = secret_manager.get_secret(settings.AMAZON_REFRESH_TOKEN_SECRET)
                profile_id = secret_manager.get_secret(settings.AMAZON_PROFILE_ID_SECRET)
                
                self._credentials = {
                    'client_id': client_id.strip(),
                    'client_secret': client_secret.strip(),
                    'refresh_token': refresh_token.strip(),
                    'profile_id': profile_id.strip()
                }
                
                logger.info(f"Using client_id: {self._credentials['client_id'][:10]}...")
                
            except Exception as e:
                logger.error(f"Failed to load credentials from Secret Manager: {e}")
                raise
        
        return self._credentials
    
    def get_access_token(self) -> str:
        """
        Get valid access token, refreshing if necessary
        Thread-safe implementation
        """
        with self._lock:
            # Check if current token is still valid
            if self._access_token and self._token_expiry:
                if datetime.now() < self._token_expiry:
                    logger.debug("Using cached access token")
                    return self._access_token
            
            # Need to refresh token
            return self._refresh_token()
    
    def _refresh_token(self) -> str:
        """Refresh the access token using refresh token"""
        credentials = self._load_credentials()
        
        url = "https://api.amazon.com/auth/o2/token"
        
        data = {
            "grant_type": "refresh_token",
            "refresh_token": credentials['refresh_token'],
            "client_id": credentials['client_id'],
            "client_secret": credentials['client_secret']
        }
        
        try:
            logger.info("Refreshing Amazon API token...")
            response = requests.post(url, data=data, timeout=30)
            
            logger.info(f"Response status: {response.status_code}")
            
            if response.status_code == 200:
                token_data = response.json()
                
                self._access_token = token_data['access_token']
                expires_in = token_data.get('expires_in', 3600)
                
                # Set expiry with 5-minute buffer
                self._token_expiry = datetime.now() + timedelta(seconds=expires_in - 300)
                
                logger.info(f"✅ Token refreshed successfully (expires in {expires_in}s)")
                return self._access_token
            
            elif response.status_code == 400:
                error_data = response.json() if response.content else {}
                error_msg = error_data.get('error_description', 'Bad Request')
                logger.error(f"❌ Token refresh failed (400): {error_msg}")
                logger.error(f"This usually means the refresh_token is invalid or expired")
                raise Exception(f"Token refresh failed: {error_msg}")
            
            else:
                logger.error(f"❌ Token refresh failed: {response.status_code} - {response.text}")
                response.raise_for_status()
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Network error during token refresh: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Unexpected error during token refresh: {e}")
            raise
    
    def invalidate_token(self):
        """Force token refresh on next request"""
        with self._lock:
            self._access_token = None
            self._token_expiry = None
            logger.info("Access token invalidated")
    
    def get_profile_id(self) -> str:
        """Get Amazon Ads profile ID from credentials"""
        credentials = self._load_credentials()
        return str(credentials['profile_id'])
    
    def get_client_id(self) -> str:
        """Get client ID from credentials"""
        credentials = self._load_credentials()
        return credentials['client_id']

# Global singleton instance
token_manager = TokenManager()
