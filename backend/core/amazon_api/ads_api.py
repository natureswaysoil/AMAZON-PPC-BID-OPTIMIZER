"""Amazon Ads API Client - WITH PAGINATION for all campaigns"""
import requests
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class AmazonAdsAPI:
    def __init__(self, credentials: Dict):
        self.client_id = credentials.get('client_id')
        self.client_secret = credentials.get('client_secret')
        self.refresh_token = credentials.get('refresh_token')
        self.profile_id = credentials.get('profile_id')
        self.region = credentials.get('region', 'NA')
        
        self.base_url = "https://advertising-api.amazon.com"
        self.access_token = None
        self.token_expiry = None
        
        self._refresh_access_token()
    
    def _refresh_access_token(self) -> str:
        """Get fresh access token"""
        logger.info("Refreshing access token...")
        
        url = "https://api.amazon.com/auth/o2/token"
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }
        
        response = requests.post(url, data=data, timeout=30)
        response.raise_for_status()
        
        token_data = response.json()
        self.access_token = token_data['access_token']
        self.token_expiry = datetime.now() + timedelta(seconds=token_data.get('expires_in', 3600) - 300)
        
        logger.info(f"✅ Token refreshed")
        return self.access_token
    
    def _get_access_token(self) -> str:
        if not self.access_token or self.token_expiry <= datetime.now():
            self._refresh_access_token()
        return self.access_token
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """Make authenticated request"""
        headers = {
            "Amazon-Advertising-API-ClientId": self.client_id,
            "Authorization": f"Bearer {self._get_access_token()}",
            "Amazon-Advertising-API-Scope": str(self.profile_id),
            "Content-Type": "application/json"
        }
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = requests.request(method, url, headers=headers, timeout=30, **kwargs)
            
            if response.status_code == 429:
                time.sleep(2)
                return self._make_request(method, endpoint, **kwargs)
            
            if response.status_code == 401:
                self._refresh_access_token()
                headers["Authorization"] = f"Bearer {self.access_token}"
                response = requests.request(method, url, headers=headers, timeout=30, **kwargs)
            
            response.raise_for_status()
            return response.json() if response.content else {}
            
        except Exception as e:
            logger.error(f"API request failed: {e}")
            raise
    
    def get_sd_campaigns_paginated(self) -> List[Dict]:
        """Get ALL SD campaigns with pagination"""
        all_campaigns = []
        next_token = None
        page = 1
        
        logger.info("Fetching SD campaigns with pagination...")
        
        while True:
            # SD API uses POST with pagination
            endpoint = "/sd/campaigns/list"
            
            payload = {
                "maxResults": 100,  # Max per page
                "stateFilter": ["ENABLED", "PAUSED", "ARCHIVED"]
            }
            
            if next_token:
                payload["nextToken"] = next_token
            
            try:
                response = self._make_request('POST', endpoint, json=payload)
                
                campaigns = response.get('campaigns', [])
                all_campaigns.extend(campaigns)
                
                logger.info(f"Page {page}: Found {len(campaigns)} campaigns (total: {len(all_campaigns)})")
                
                next_token = response.get('nextToken')
                
                if not next_token:
                    break
                
                page += 1
                time.sleep(0.5)  # Rate limiting courtesy
                
            except Exception as e:
                logger.error(f"Failed to fetch SD campaigns page {page}: {e}")
                # Try old endpoint as fallback
                if page == 1:
                    try:
                        campaigns = self._make_request('GET', '/sd/campaigns')
                        all_campaigns.extend(campaigns)
                    except:
                        pass
                break
        
        logger.info(f"✅ Total SD campaigns fetched: {len(all_campaigns)}")
        return all_campaigns
    
    def get_campaigns(self) -> List[Dict]:
        """Get all campaigns from all available endpoints"""
        all_campaigns = []
        
        # Get SD campaigns with pagination
        try:
            sd_campaigns = self.get_sd_campaigns_paginated()
            all_campaigns.extend(sd_campaigns)
            logger.info(f"SD campaigns: {len(sd_campaigns)}")
        except Exception as e:
            logger.error(f"SD campaigns failed: {e}")
        
        # Try SP campaigns (might not be available for your account)
        try:
            sp_campaigns = self._make_request('GET', '/v2/sp/campaigns')
            all_campaigns.extend(sp_campaigns)
            logger.info(f"SP campaigns: {len(sp_campaigns)}")
        except:
            pass
        
        return all_campaigns
    
    def get_keywords(self) -> List[Dict]:
        """Get keywords/targets with pagination"""
        all_targets = []
        
        # SD targets with pagination
        try:
            next_token = None
            page = 1
            
            while True:
                endpoint = "/sd/targets/list"
                payload = {
                    "maxResults": 100,
                    "stateFilter": ["ENABLED", "PAUSED", "ARCHIVED"]
                }
                
                if next_token:
                    payload["nextToken"] = next_token
                
                response = self._make_request('POST', endpoint, json=payload)
                targets = response.get('targets', [])
                all_targets.extend(targets)
                
                logger.info(f"Targets page {page}: {len(targets)} (total: {len(all_targets)})")
                
                next_token = response.get('nextToken')
                if not next_token:
                    break
                
                page += 1
                time.sleep(0.5)
                
        except Exception as e:
            logger.error(f"Failed to fetch targets: {e}")
        
        return all_targets
