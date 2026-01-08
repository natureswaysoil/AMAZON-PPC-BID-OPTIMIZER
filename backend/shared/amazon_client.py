# backend/shared/amazon_client.py
"""
Unified Amazon Advertising API Client
Uses TokenManager for authentication
Includes rate limiting, retries, and comprehensive error handling
"""
import requests
import time
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
from shared.token_manager import token_manager

logger = logging.getLogger(__name__)

class AmazonAdsClient:
    """
    Amazon Advertising API client with automatic authentication
    
    Features:
    - Automatic token refresh
    - Rate limiting handling
    - Retry logic with exponential backoff
    - Comprehensive logging
    """
    
    def __init__(self, region: str = "NA"):
        self.region = region
        self.base_url = "https://advertising-api.amazon.com"
        self._request_count = 0
        logger.info("✅ AmazonAdsClient initialized")
    
    def _get_headers(self) -> Dict[str, str]:
        """Build request headers with current access token"""
        return {
            "Amazon-Advertising-API-ClientId": token_manager.get_client_id(),
            "Authorization": f"Bearer {token_manager.get_access_token()}",
            "Amazon-Advertising-API-Scope": token_manager.get_profile_id(),
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        max_retries: int = 3,
        **kwargs
    ) -> Any:
        """
        Make authenticated request to Amazon Ads API
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (e.g., '/v2/sp/keywords')
            max_retries: Maximum number of retry attempts
            **kwargs: Additional arguments for requests
        
        Returns:
            Response data (dict or list)
        
        Raises:
            requests.HTTPError: On non-recoverable HTTP errors
        """
        url = f"{self.base_url}{endpoint}"
        self._request_count += 1
        
        for attempt in range(max_retries):
            try:
                headers = self._get_headers()
                
                logger.debug(f"{method} {endpoint} (attempt {attempt + 1}/{max_retries})")
                
                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    timeout=30,
                    **kwargs
                )
                
                # Handle rate limiting (429)
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    logger.warning(f"⚠️ Rate limited. Waiting {retry_after}s before retry...")
                    time.sleep(retry_after)
                    continue
                
                # Handle unauthorized (401) - token might be expired
                if response.status_code == 401:
                    logger.warning("⚠️ Received 401 Unauthorized. Invalidating token and retrying...")
                    token_manager.invalidate_token()
                    
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)  # Exponential backoff
                        continue
                
                # Raise for other HTTP errors
                response.raise_for_status()
                
                # Success - return response data
                if response.content:
                    return response.json()
                else:
                    return {}
                
            except requests.exceptions.HTTPError as e:
                logger.error(f"❌ HTTP error on {method} {endpoint}: {e}")
                
                if attempt == max_retries - 1:
                    raise
                
                # Wait before retry (exponential backoff)
                wait_time = 2 ** attempt
                logger.info(f"Retrying in {wait_time}s...")
                time.sleep(wait_time)
            
            except requests.exceptions.RequestException as e:
                logger.error(f"❌ Network error on {method} {endpoint}: {e}")
                
                if attempt == max_retries - 1:
                    raise
                
                time.sleep(2 ** attempt)
        
        raise Exception(f"Max retries ({max_retries}) exceeded for {method} {endpoint}")
    
    # ===== Campaigns API =====
    
    def get_campaigns(self, state_filter: Optional[str] = "enabled") -> List[Dict]:
        """
        Get all campaigns
        
        Args:
            state_filter: Filter by state ('enabled', 'paused', 'archived')
        
        Returns:
            List of campaign dictionaries
        """
        params = {}
        if state_filter:
            params['stateFilter'] = state_filter
        
        logger.info(f"Fetching campaigns (state={state_filter})...")
        response = self._make_request('GET', '/v2/sp/campaigns', params=params)
        
        campaigns = response if isinstance(response, list) else []
        logger.info(f"✅ Retrieved {len(campaigns)} campaigns")
        return campaigns
    
    # ===== Keywords API =====
    
    def get_keywords(
        self, 
        campaign_id: Optional[int] = None,
        state_filter: Optional[str] = "enabled"
    ) -> List[Dict]:
        """
        Get keywords, optionally filtered by campaign
        
        Args:
            campaign_id: Filter by campaign ID
            state_filter: Filter by state
        
        Returns:
            List of keyword dictionaries
        """
        params = {}
        if state_filter:
            params['stateFilter'] = state_filter
        if campaign_id:
            params['campaignIdFilter'] = campaign_id
        
        logger.info(f"Fetching keywords (campaign={campaign_id}, state={state_filter})...")
        response = self._make_request('GET', '/v2/sp/keywords', params=params)
        
        keywords = response if isinstance(response, list) else []
        logger.info(f"✅ Retrieved {len(keywords)} keywords")
        return keywords
    
    def update_keyword_bid(self, keyword_id: int, new_bid: float) -> Dict:
        """
        Update keyword bid
        
        Args:
            keyword_id: Keyword ID to update
            new_bid: New bid amount
        
        Returns:
            Update response
        """
        data = [{
            "keywordId": keyword_id,
            "bid": round(new_bid, 2)
        }]
        
        logger.info(f"Updating keyword {keyword_id} bid to ${new_bid:.2f}")
        response = self._make_request('PUT', '/v2/sp/keywords', json=data)
        logger.info(f"✅ Keyword bid updated")
        return response
    
    def update_keyword_bids_batch(self, updates: List[Dict]) -> Dict:
        """
        Update multiple keyword bids in one request
        
        This method accepts optimization dictionaries and converts them to Amazon API format.
        
        Args:
            updates: List of dicts with ONE of these formats:
                     1. Amazon API format: {'keywordId': 123, 'bid': 1.50}
                     2. Python-style: {'keyword_id': 123, 'new_bid': 1.50}
                     
                     The optimizer returns format #2, which is automatically converted.
        
        Returns:
            Batch update response
        
        Raises:
            ValueError: If required keys are missing from any update dict
        
        Example:
            # Direct from optimizer
            optimizations = optimizer.optimize_all_keywords()
            client.update_keyword_bids_batch(optimizations)
            
            # Or with explicit format
            updates = [{'keyword_id': 123, 'new_bid': 1.50}]
            client.update_keyword_bids_batch(updates)
        """
        # Support both Amazon API format and Python-style keys
        data = []
        for i, u in enumerate(updates):
            if 'keywordId' in u and 'bid' in u:
                # Already in Amazon API format
                data.append({
                    "keywordId": u['keywordId'],
                    "bid": round(u['bid'], 2)
                })
            elif 'keyword_id' in u and 'new_bid' in u:
                # Convert from Python-style keys (optimizer format)
                data.append({
                    "keywordId": u['keyword_id'],
                    "bid": round(u['new_bid'], 2)
                })
            else:
                # Missing required keys
                raise ValueError(
                    f"Update dict at index {i} missing required keys. "
                    f"Expected either ('keywordId', 'bid') or ('keyword_id', 'new_bid'), "
                    f"but got: {list(u.keys())}"
                )
        
        logger.info(f"Batch updating {len(updates)} keyword bids")
        response = self._make_request('PUT', '/v2/sp/keywords', json=data)
        logger.info(f"✅ Batch update complete")
        return response
    
    # ===== Bid Recommendations API =====
    
    def get_keyword_bid_recommendations(
        self,
        keyword_ids: List[int],
        ad_group_id: int
    ) -> Dict[int, Dict]:
        """
        Get Amazon's bid recommendations for keywords
        
        Args:
            keyword_ids: List of keyword IDs to get recommendations for
            ad_group_id: Ad group ID these keywords belong to
        
        Returns:
            Dict mapping keyword_id to recommendation data:
            {
                keyword_id: {
                    'suggested_bid': float,
                    'range_start': float,
                    'range_end': float,
                    'confidence': str
                }
            }
        """
        # Amazon Ads API v2 bid recommendations endpoint
        endpoint = '/v2/sp/keywords/bidRecommendations'
        
        data = {
            'adGroupId': ad_group_id,
            'keywords': [{'keywordId': kid} for kid in keyword_ids]
        }
        
        logger.info(f"Fetching bid recommendations for {len(keyword_ids)} keywords...")
        
        try:
            response = self._make_request('POST', endpoint, json=data)
            
            recommendations = {}
            
            if 'recommendations' in response:
                for rec in response['recommendations']:
                    keyword_id = rec.get('keywordId')
                    
                    if keyword_id and 'suggestedBid' in rec:
                        recommendations[keyword_id] = {
                            'suggested_bid': float(rec['suggestedBid']),
                            'range_start': float(rec.get('rangeStart', 0)),
                            'range_end': float(rec.get('rangeEnd', 0)),
                            'confidence': rec.get('confidence', 'MEDIUM')
                        }
            
            logger.info(f"✅ Retrieved {len(recommendations)} bid recommendations")
            return recommendations
            
        except Exception as e:
            logger.warning(f"⚠️ Failed to get bid recommendations: {e}")
            # Return empty dict - optimizer will fall back to AOV-only calculation
            return {}
    
    def get_keyword_bid_recommendations_batch(
        self,
        keywords: List[Dict]
    ) -> Dict[int, Dict]:
        """
        Get bid recommendations for multiple keywords across ad groups
        
        Args:
            keywords: List of dicts with 'keyword_id' and 'ad_group_id'
        
        Returns:
            Dict mapping keyword_id to recommendation data
        """
        # Group by ad group for batching
        by_ad_group = {}
        for kw in keywords:
            ag_id = kw['ad_group_id']
            if ag_id not in by_ad_group:
                by_ad_group[ag_id] = []
            by_ad_group[ag_id].append(kw['keyword_id'])
        
        all_recommendations = {}
        
        # Fetch recommendations per ad group
        for ad_group_id, keyword_ids in by_ad_group.items():
            # Process in chunks of 100 (API limit)
            chunk_size = 100
            for i in range(0, len(keyword_ids), chunk_size):
                chunk = keyword_ids[i:i + chunk_size]
                recs = self.get_keyword_bid_recommendations(chunk, ad_group_id)
                all_recommendations.update(recs)
        
        return all_recommendations
    
    # ===== Ad Groups API =====
    
    def get_ad_groups(self, campaign_id: Optional[int] = None) -> List[Dict]:
        """Get ad groups, optionally filtered by campaign"""
        params = {}
        if campaign_id:
            params['campaignIdFilter'] = campaign_id
        
        logger.info(f"Fetching ad groups...")
        response = self._make_request('GET', '/v2/sp/adGroups', params=params)
        return response if isinstance(response, list) else []
    
    # ===== Reporting API =====
    
    def request_report(
        self,
        record_type: str,
        metrics: List[str],
        report_date: str,
        segment: Optional[str] = None
    ) -> str:
        """
        Request a report
        
        Args:
            record_type: Type of report ('campaigns', 'keywords', 'adGroups')
            metrics: List of metrics to include
            report_date: Date for report (YYYYMMDD format)
            segment: Optional segment (e.g., 'query' for search terms)
        
        Returns:
            Report ID
        """
        data = {
            "reportDate": report_date,
            "metrics": ",".join(metrics)
        }
        
        if segment:
            data["segment"] = segment
        
        endpoint = f"/v2/sp/{record_type}/report"
        logger.info(f"Requesting {record_type} report for {report_date}")
        
        response = self._make_request('POST', endpoint, json=data)
        report_id = response.get('reportId')
        
        logger.info(f"✅ Report requested: {report_id}")
        return report_id
    
    def get_report_status(self, report_id: str) -> Dict:
        """Check report generation status"""
        endpoint = f"/v2/reports/{report_id}"
        return self._make_request('GET', endpoint)
    
    def download_report(self, report_id: str, max_wait: int = 300) -> Dict:
        """
        Download completed report (with polling)
        
        Args:
            report_id: Report ID from request_report
            max_wait: Maximum seconds to wait for completion
        
        Returns:
            Report data as dict
        """
        start_time = time.time()
        
        while (time.time() - start_time) < max_wait:
            status_response = self.get_report_status(report_id)
            status = status_response.get('status')
            
            if status == 'SUCCESS':
                report_url = status_response['location']
                logger.info(f"✅ Report ready. Downloading...")
                
                # Amazon returns pre-signed URLs containing temporary authentication
                # credentials in the URL parameters, so no additional headers are needed
                report_data = requests.get(report_url, timeout=60)
                report_data.raise_for_status()
                
                return report_data.json()
            
            elif status == 'FAILURE':
                raise Exception(f"Report generation failed: {status_response}")
            
            elif status in ['IN_PROGRESS', 'PENDING']:
                logger.debug(f"Report {status}, waiting...")
                time.sleep(10)
            else:
                logger.warning(f"Unknown report status: {status}")
                time.sleep(10)
        
        raise TimeoutError(f"Report {report_id} not ready after {max_wait}s")
    
    # ===== Utility Methods =====
    
    def get_request_count(self) -> int:
        """Get number of API requests made"""
        return self._request_count

# Global singleton instance
amazon_client = AmazonAdsClient()
