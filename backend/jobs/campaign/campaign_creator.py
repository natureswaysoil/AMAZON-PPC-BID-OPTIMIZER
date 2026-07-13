"""Campaign Creator - Launch campaigns to Amazon Ads API"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from ..campaign.campaign_engine import build_campaign_plan, load_products_from_sheet, first, product_name

logger = logging.getLogger(__name__)


class CampaignCreator:
    """Create and launch campaigns via Amazon Ads API"""
    
    def __init__(self, amazon_client):
        self.client = amazon_client
    
    def create_campaign(self, campaign_config: Dict[str, Any], 
                       product_asin: str,
                       product_sku: str,
                       dry_run: bool = True) -> Dict[str, Any]:
        """Create a single campaign"""
        try:
            if dry_run:
                return {
                    "status": "dry_run",
                    "campaign_name": campaign_config.get("campaign_name"),
                    "campaign_type": campaign_config.get("campaign_type"),
                    "daily_budget": campaign_config.get("daily_budget"),
                    "keyword_count": campaign_config.get("keyword_count"),
                    "estimated_spend": campaign_config.get("daily_budget") * 30,
                }
            
            # Create campaign via Amazon Ads API
            campaign_request = {
                "name": campaign_config.get("campaign_name"),
                "budget": {
                    "budgetType": "DAILY",
                    "budget": campaign_config.get("daily_budget")
                },
                "state": "ENABLED",
                "portfolioId": None,
                "adProduct": "SPONSORED_PRODUCTS"
            }
            
            response = self.client._make_request(
                method="POST",
                endpoint="/sp/campaigns",
                json=campaign_request,
            )
            
            campaign_id = response.get("campaignId")
            if not campaign_id:
                raise ValueError("No campaign ID returned from Amazon API")
            
            return {
                "status": "created",
                "campaign_id": campaign_id,
                "campaign_name": campaign_config.get("campaign_name"),
                "campaign_type": campaign_config.get("campaign_type"),
                "daily_budget": campaign_config.get("daily_budget"),
                "keyword_count": campaign_config.get("keyword_count"),
            }
        
        except Exception as e:
            logger.error(f"Failed to create campaign {campaign_config.get('campaign_name')}: {e}")
            return {
                "status": "failed",
                "campaign_name": campaign_config.get("campaign_name"),
                "error": str(e)
            }
    
    def create_ad_group(self, campaign_id: str, ad_group_name: str, 
                       default_bid: float, dry_run: bool = True) -> Dict[str, Any]:
        """Create an ad group in the campaign"""
        try:
            if dry_run:
                return {
                    "status": "dry_run",
                    "ad_group_name": ad_group_name,
                    "default_bid": default_bid,
                }
            
            ad_group_request = {
                "campaignId": campaign_id,
                "name": ad_group_name,
                "state": "ENABLED",
                "defaultBid": default_bid
            }
            
            response = self.client._make_request(
                method="POST",
                endpoint="/sp/adGroups",
                json=ad_group_request,
            )
            
            ad_group_id = response.get("adGroupId")
            if not ad_group_id:
                raise ValueError("No ad group ID returned from Amazon API")
            
            return {
                "status": "created",
                "ad_group_id": ad_group_id,
                "ad_group_name": ad_group_name,
                "default_bid": default_bid,
            }
        
        except Exception as e:
            logger.error(f"Failed to create ad group {ad_group_name}: {e}")
            return {
                "status": "failed",
                "ad_group_name": ad_group_name,
                "error": str(e)
            }
    
    def create_keywords(self, ad_group_id: str, keywords: List[Dict[str, Any]], 
                       dry_run: bool = True) -> Dict[str, Any]:
        """Create keywords in the ad group"""
        try:
            if dry_run:
                return {
                    "status": "dry_run",
                    "keyword_count": len(keywords),
                    "keywords": keywords[:5],
                }
            
            created_count = 0
            failed_count = 0
            
            for kw in keywords:
                try:
                    kw_request = {
                        "adGroupId": ad_group_id,
                        "keywordText": kw.get("keywordText"),
                        "matchType": kw.get("matchType", "exact"),
                        "state": "ENABLED",
                        "bid": kw.get("bid", 0.50)
                    }
                    
                    response = self.client._make_request(
                        method="POST",
                        endpoint="/sp/keywords",
                        json=kw_request,
                    )
                    
                    if response.get("keywordId"):
                        created_count += 1
                    else:
                        failed_count += 1
                
                except Exception as e:
                    logger.warning(f"Failed to create keyword {kw.get('keywordText')}: {e}")
                    failed_count += 1
            
            return {
                "status": "created",
                "total": len(keywords),
                "created": created_count,
                "failed": failed_count,
            }
        
        except Exception as e:
            logger.error(f"Failed to create keywords: {e}")
            return {
                "status": "failed",
                "total": len(keywords),
                "error": str(e)
            }
    
    def launch_campaign_from_product(self, product_sku: str, 
                                    daily_budget: Optional[float] = None,
                                    starting_bid: Optional[float] = None,
                                    dry_run: bool = True) -> Dict[str, Any]:
        """Launch a complete campaign setup from product sheet data"""
        try:
            # Load products and find matching product
            products = load_products_from_sheet()
            product = None
            for p in products:
                if first(p, "SKU") == product_sku:
                    product = p
                    break
            
            if not product:
                return {"status": "failed", "error": f"Product {product_sku} not found"}
            
            # Build campaign plan
            plan = build_campaign_plan(product)
            
            # Override budget/bid if provided
            if daily_budget:
                for campaign in plan["campaigns"]:
                    campaign["daily_budget"] = daily_budget
            
            if starting_bid:
                for campaign in plan["campaigns"]:
                    campaign["default_bid"] = starting_bid
            
            results = {
                "product_name": plan["product_name"],
                "product_sku": product_sku,
                "total_campaigns": len(plan["campaigns"]),
                "campaigns": [],
                "dry_run": dry_run,
                "timestamp": datetime.utcnow().isoformat(),
            }
            
            # Create each campaign
            for campaign_config in plan["campaigns"]:
                campaign_result = self.create_campaign(
                    campaign_config, 
                    product.get("ASIN", ""),
                    product_sku,
                    dry_run=dry_run
                )
                results["campaigns"].append(campaign_result)
                
                # If not dry run, create ad group and keywords
                if not dry_run and campaign_result.get("status") == "created":
                    campaign_id = campaign_result.get("campaign_id")
                    ad_group_result = self.create_ad_group(
                        campaign_id,
                        f"AG_{campaign_config.get('campaign_type')}",
                        campaign_config.get("default_bid"),
                        dry_run=False
                    )
                    campaign_result["ad_group"] = ad_group_result
                    
                    if ad_group_result.get("status") == "created":
                        keywords_result = self.create_keywords(
                            ad_group_result.get("ad_group_id"),
                            campaign_config.get("keywords", []),
                            dry_run=False
                        )
                        campaign_result["keywords"] = keywords_result
            
            return results
        
        except Exception as e:
            logger.error(f"Failed to launch campaign from product {product_sku}: {e}")
            return {
                "status": "failed",
                "product_sku": product_sku,
                "error": str(e)
            }
    
    def get_products_preview(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get preview of available products from sheet"""
        try:
            products = load_products_from_sheet()
            preview = []
            for p in products[:limit]:
                plan = build_campaign_plan(p)
                preview.append({
                    "sku": first(p, "SKU"),
                    "asin": first(p, "ASIN"),
                    "product_name": plan["product_name"],
                    "total_keywords": plan["total_keywords"],
                    "campaign_count": len(plan["campaigns"]),
                    "estimated_daily_budget": sum(c.get("daily_budget", 0) for c in plan["campaigns"]),
                })
            return preview
        except Exception as e:
            logger.error(f"Failed to get products preview: {e}")
            return []
